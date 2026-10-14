"""CyberPaw admin home: one page with competition status, the challenge list and an inline
"Add challenge" form.

It extends the platform's admin base template, so the admin menu and scripts stay in place. The
platform's own admin pages remain reachable; this is a simpler front end on top of the same data.
"""
import datetime
import os

from flask import Blueprint, abort, jsonify, redirect, render_template_string, request, url_for
from sqlalchemy import func

from .platform_api import (
    ChallengeFiles, Challenges, DynamicChallenge, Fails, Flags, Ratings, Solves, Users,
    admins_only, clear_challenges, clear_config, clear_standings, db, delete_file, get_config,
    is_admin, set_config, upload_file,
)

from .bonus_flag import CyberpawBonusFlag, set_bonus
from .release import CyberpawChallengeRelease

TEMPLATES = os.path.join(os.path.dirname(__file__), "templates")
DIFFICULTY_LABELS = {1: "1 - Easy", 2: "2", 3: "3 - Medium", 4: "4", 5: "5 - Hard"}

admin_pages = Blueprint("cyberpaw_admin", __name__)


def render(name, **context):
    with open(os.path.join(TEMPLATES, name)) as f:
        return render_template_string(f.read(), **context)


def meta_model():
    # Imported here to avoid a circular import with the package __init__.
    from . import CyberpawChallengeMeta

    return CyberpawChallengeMeta


def home_url(category=None, challenge_id=None, **args):
    url = url_for("cyberpaw_admin.home", open=category, **args)
    return url + (f"#chal-{challenge_id}" if challenge_id else "")


def page_context():
    now = datetime.datetime.utcnow()
    start, end = get_config("start"), get_config("end")
    ts_now = now.timestamp()
    if get_config("paused"):
        state = ("Paused", "warning")
    elif start and ts_now < int(start):
        state = ("Not started", "secondary")
    elif end and ts_now > int(end):
        state = ("Ended", "secondary")
    else:
        state = ("Running", "success")

    Meta = meta_model()
    solves = dict(
        db.session.query(Solves.challenge_id, func.count(Solves.id)).group_by(Solves.challenge_id)
    )
    difficulty = dict(db.session.query(Meta.challenge_id, Meta.difficulty))
    bonus = dict(db.session.query(CyberpawBonusFlag.challenge_id, CyberpawBonusFlag.points))
    # Player ratings: thumbs up/down counts and the optional written reviews, newest first. Admins only.
    ratings = {}
    rows = (
        db.session.query(Ratings, Users.id, Users.name)
        .join(Users, Users.id == Ratings.user_id)
        .order_by(Ratings.date.desc())
    )
    for rating, user_id, user_name in rows:
        r = ratings.setdefault(rating.challenge_id, {"up": 0, "down": 0, "reviews": []})
        if rating.value == 1:
            r["up"] += 1
        elif rating.value == -1:
            r["down"] += 1
        if rating.review and rating.review.strip():
            r["reviews"].append(
                {"user_id": user_id, "user": user_name, "value": rating.value, "text": rating.review, "date": rating.date}
            )
    categories = {}
    for chal in Challenges.query.order_by(Challenges.category, Challenges.value).all():
        categories.setdefault(chal.category or "Uncategorized", []).append(
            {
                "id": chal.id,
                "name": chal.name,
                "value": chal.value,
                "dynamic": chal.type == "dynamic",
                "visible": chal.state == "visible",
                "difficulty": difficulty.get(chal.id, 0),
                "bonus": bonus.get(chal.id),
                "solves": solves.get(chal.id, 0),
                "ratings": ratings.get(chal.id, {"up": 0, "down": 0, "reviews": []}),
            }
        )

    return dict(
        state=state,
        registration_open=get_config("registration_visibility") == "public",
        paused=bool(get_config("paused")),
        live_countdown=bool(get_config("cp_live_countdown")),
        players=Users.query.filter_by(type="user").count(),
        total_solves=Solves.query.count(),
        wrong_today=Fails.query.filter(Fails.date >= now - datetime.timedelta(hours=24)).count(),
        categories=categories,
        difficulty_labels=DIFFICULTY_LABELS,
        form={},
        errors=[],
    )


@admin_pages.route("/admin/cyberpaw")
@admins_only
def home():
    return render("home.html", **page_context())


@admin_pages.route("/admin/cyberpaw/referrals")
@admins_only
def referrals():
    """Referral data for the admin Users page columns (assets/admin.js). Empty when the setting is off."""
    from .referral import ADMIN_COLUMNS_SETTING, admin_overview

    if not get_config(ADMIN_COLUMNS_SETTING):
        return jsonify(enabled=False)
    return jsonify(enabled=True, **admin_overview()), 200, {"Cache-Control": "no-store"}


# System graph: a map of every server, service and file behind the site. It names internal details, so it
# is never committed (the repo is public). An admin copies it to this path on the server; see .gitignore.
SYSTEM_GRAPH = os.path.join(os.path.dirname(__file__), "system-graph.html")


@admin_pages.route("/admin/cyberpaw/graph")
@admins_only
def system_graph():
    if not os.path.isfile(SYSTEM_GRAPH):
        abort(404)
    with open(SYSTEM_GRAPH) as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}


# The switches on the admin home call these with JSON {"on": true|false} and get the new state back.
def switch_value():
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("on"), bool):
        abort(400)
    return body["on"]


@admin_pages.route("/admin/cyberpaw/registration", methods=["POST"])
@admins_only
def set_registration():
    is_open = switch_value()
    set_config("registration_visibility", "public" if is_open else "private")
    clear_config()
    return jsonify(success=True, on=is_open)


@admin_pages.route("/admin/cyberpaw/competition", methods=["POST"])
@admins_only
def set_competition():
    running = switch_value()
    set_config("paused", not running)
    clear_config()
    clear_challenges()
    clear_standings()
    return jsonify(success=True, on=running)


# Off by default: once the competition is live, the home page drops the "Live now · ends in" card.
@admin_pages.route("/admin/cyberpaw/live-countdown", methods=["POST"])
@admins_only
def set_live_countdown():
    shown = switch_value()
    set_config("cp_live_countdown", shown)
    clear_config()
    return jsonify(success=True, on=shown)


@admin_pages.route("/admin/cyberpaw/challenges/<int:challenge_id>/visible", methods=["POST"])
@admins_only
def set_challenge_visible(challenge_id):
    chal = Challenges.query.filter_by(id=challenge_id).first_or_404()
    visible = switch_value()
    chal.state = "visible" if visible else "hidden"
    CyberpawChallengeRelease.query.filter_by(challenge_id=challenge_id).delete()
    db.session.commit()
    clear_challenges()
    clear_standings()
    return jsonify(success=True, on=visible)


# Release time field on the challenge edit page (assets/admin.js). POST {"at": epoch seconds or null}.
@admin_pages.route("/admin/cyberpaw/challenges/<int:challenge_id>/release", methods=["GET", "POST"])
@admins_only
def challenge_release(challenge_id):
    chal = Challenges.query.filter_by(id=challenge_id).first_or_404()
    row = CyberpawChallengeRelease.query.filter_by(challenge_id=challenge_id).first()
    if request.method == "POST":
        at = (request.get_json(silent=True) or {}).get("at")
        if at is None:
            if row is not None:
                db.session.delete(row)
            row = None
        else:
            errors = []
            when = release_time({"release_at": str(at)}, errors)
            if chal.state == "visible":
                errors.append("This challenge is already visible. Hide it first, then set a release time.")
            if errors:
                return jsonify(success=False, message=" ".join(errors)), 400
            if row is None:
                row = CyberpawChallengeRelease(challenge_id=challenge_id)
                db.session.add(row)
            row.release_at = when
        db.session.commit()
    at = int(row.release_at.replace(tzinfo=datetime.timezone.utc).timestamp()) if row else None
    return jsonify(success=True, at=at, visible=chal.state == "visible"), 200, {"Cache-Control": "no-store"}


# Bonus flag fields on the challenge edit page (assets/admin.js). POST {"flag": text or null, "points": number}.
@admin_pages.route("/admin/cyberpaw/challenges/<int:challenge_id>/bonus", methods=["GET", "POST"])
@admins_only
def challenge_bonus(challenge_id):
    Challenges.query.filter_by(id=challenge_id).first_or_404()
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        errors = []
        flag, points = bonus_fields(
            {"bonus_flag": str(body.get("flag") or ""), "bonus_points": str(body.get("points", ""))}, errors
        )
        if flag and Flags.query.filter_by(challenge_id=challenge_id, content=flag).first():
            errors.append("The bonus flag must be different from the challenge's flag.")
        if errors:
            return jsonify(success=False, message=" ".join(errors)), 400
        set_bonus(challenge_id, flag, points)
        db.session.commit()
    row = CyberpawBonusFlag.query.filter_by(challenge_id=challenge_id).first()
    return (
        jsonify(success=True, flag=row.content if row else None, points=row.points if row else None),
        200,
        {"Cache-Control": "no-store"},
    )


def int_field(form, key, errors, label, minimum=0):
    try:
        value = int(form.get(key, ""))
    except ValueError:
        errors.append(f"{label} must be a whole number.")
        return None
    if value < minimum:
        errors.append(f"{label} must be at least {minimum}.")
    return value


def bonus_fields(form, errors):
    """The form's bonus flag and its points, or (None, None) when no bonus flag is set."""
    flag = form.get("bonus_flag", "").strip()
    if not flag:
        return None, None
    if len(flag) > 255:
        errors.append("Bonus flag must be 255 characters or less.")
    return flag, int_field(form, "bonus_points", errors, "Bonus points", 1)


def release_time(form, errors):
    """The form's release time as a UTC datetime, or None when not set."""
    raw = form.get("release_at", "").strip()
    if not raw:
        return None
    try:
        when = datetime.datetime.utcfromtimestamp(int(raw))
    except (ValueError, OverflowError, OSError):
        errors.append("Release time is not valid.")
        return None
    if when <= datetime.datetime.utcnow():
        errors.append("Release time must be in the future.")
    if form.get("visible"):
        errors.append("Pick either a release time or visible now, not both.")
    return when




def validate(form):
    errors = []
    for key, label in (("name", "Name"), ("category", "Category"), ("flag", "Flag")):
        if not form.get(key, "").strip():
            errors.append(f"{label} is required.")
    if len(form.get("name", "")) > 80 or len(form.get("category", "")) > 80:
        errors.append("Name and category must be 80 characters or less.")
    if form.get("scoring") == "dynamic":
        initial = int_field(form, "initial", errors, "Starting points", 1)
        minimum = int_field(form, "minimum", errors, "Minimum points", 0)
        int_field(form, "decay", errors, "Decay", 1)
        if initial is not None and minimum is not None and minimum > initial:
            errors.append("Minimum points can't be more than starting points.")
    else:
        int_field(form, "points", errors, "Points", 0)
    if form.get("difficulty", "0") not in {"0", "1", "2", "3", "4", "5"}:
        errors.append("Pick a difficulty from the list.")
    release_time(form, errors)
    bonus_flag, _points = bonus_fields(form, errors)
    if bonus_flag and bonus_flag == form.get("flag", "").strip():
        errors.append("The bonus flag must be different from the flag.")
    return errors


def create_from_form(form, uploads):
    common = dict(
        name=form["name"].strip(),
        category=form["category"].strip(),
        description=form.get("description", ""),
        state="visible" if form.get("visible") else "hidden",
    )
    if form.get("scoring") == "dynamic":
        chal = DynamicChallenge(
            initial=int(form["initial"]),
            minimum=int(form["minimum"]),
            decay=int(form["decay"]),
            function=form.get("function") if form.get("function") in ("linear", "logarithmic") else "logarithmic",
            **common,
        )
    else:
        chal = Challenges(type="standard", value=int(form["points"]), **common)
    db.session.add(chal)
    db.session.flush()

    # Exact-match flag. Hints, tags and regex or case-insensitive flags can be added in the full challenge editor.
    db.session.add(Flags(challenge_id=chal.id, type="static", content=form["flag"].strip(), data=""))
    level = int(form.get("difficulty", "0"))
    if level:
        db.session.add(meta_model()(challenge_id=chal.id, difficulty=level))
    when = release_time(form, [])
    if when:
        db.session.add(CyberpawChallengeRelease(challenge_id=chal.id, release_at=when))
    bonus_flag, bonus_points = bonus_fields(form, [])
    if bonus_flag:
        set_bonus(chal.id, bonus_flag, bonus_points)
    db.session.commit()

    # Files are stored after the database rows exist. If any upload fails, remove the whole
    # challenge so nothing is left half-created.
    try:
        for upload in uploads:
            if upload and upload.filename:
                upload_file(file=upload, type="challenge", challenge_id=chal.id)
    except Exception:
        for f in ChallengeFiles.query.filter_by(challenge_id=chal.id).all():
            delete_file(f.id)
        # Bulk delete: the database cascade removes the flag, hint and tags (session.delete would leave them
        # behind with an empty challenge_id).
        Challenges.query.filter_by(id=chal.id).delete(synchronize_session=False)
        db.session.commit()
        raise
    clear_challenges()
    return chal


@admin_pages.route("/admin/cyberpaw/challenges/new", methods=["GET", "POST"])
@admins_only
def new_challenge():
    if request.method == "GET":
        return redirect(url_for("cyberpaw_admin.home", add=1))
    errors = validate(request.form)
    if not errors:
        try:
            chal = create_from_form(request.form, request.files.getlist("files"))
        except Exception as e:  # noqa: BLE001 - shown to the admin, challenge already rolled back
            errors.append(f"Upload failed, nothing was saved: {e}")
        else:
            return redirect(home_url(chal.category, chal.id, created=chal.id))
    context = page_context()
    context.update(form=request.form, errors=errors)
    return render("home.html", **context)


@admin_pages.before_app_request
def admin_home():
    # Send the plain /admin URL to the CyberPaw admin home instead of the statistics page.
    if request.path in ("/admin", "/admin/") and is_admin():
        return redirect(url_for("cyberpaw_admin.home"))
    return None

