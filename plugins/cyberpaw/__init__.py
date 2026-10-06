"""CyberPaw additions to the CTF platform.

Adds a 1-5 difficulty rating to challenges, like the 2024 site:
- table `cyberpaw_challenge_meta` (one row per rated challenge, removed with the challenge)
- GET  /plugins/cyberpaw/api/difficulty        {challenge_id: level} for challenges the viewer can see
- PUT  /plugins/cyberpaw/api/difficulty/<id>   admins only, body {"difficulty": 1-5 or null}
- a Difficulty dropdown on the admin challenge create and edit pages (assets/admin.js)
- GET  /plugins/cyberpaw/api/first-paws         challenges a player solved first ("First Paw")

First solve bonus (first_paw.py): optional extra points for each First Paw, set in Config -> Challenges.

Admin pages (admin_pages.py): /admin/cyberpaw dashboard, challenge list with a visible/hidden
toggle, and a one-page challenge upload form. CyberPaw styling and a shorter menu (assets/).

Player profiles (profile.py): generated avatar, short bio, GitHub and LinkedIn links.

Emails get a CyberPaw HTML version with the logo and buttons instead of long links (email/).

Email confirmation: signing up sends one email (the confirm link; the platform's extra "registered"
email is turned off). Until the account is confirmed, the player can only see the confirm page, the
text pages (Rules, How to Play, ...) and log out. The confirm link only works in a browser that is
logged in to that same account; anywhere else it asks the player to log in first
(templates/confirm_login.html in the theme). JWU's mail scanner opens every link in incoming email and
even presses buttons, but it is never logged in, so it can't confirm accounts.

Also turns off the platform's API access tokens: the token endpoints return 404 and any request that sends
an Authorization header is refused. The site's own pages use the session cookie, not tokens.
"""
import hashlib
import os
import re

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from sqlalchemy import event

# Importing these modules registers their tables, which load() creates with create_all().
from .first_paw import first_solvers, install as install_first_paw
from .profile import install as install_profiles
from .platform_api import (
    Challenges, UserConfirmTokenInvalidException, Users, admins_only, authed, check_challenge_visibility, check_score_visibility, db,
    during_ctf_time_only, get_config, get_current_user, is_admin, override_template, platform_email,
    register_admin_plugin_script, register_admin_plugin_stylesheet,
    register_plugin_assets_directory, require_verified_emails, verify_email_confirm_token,
)

HERE = os.path.dirname(__file__)
# Everyone is from JWU, so new accounts start with the JWU website. Players can change it.
DEFAULT_WEBSITE = "https://www.jwu.edu"

# Platform name and documentation links that still appear in some upstream admin help texts.
# Replaced in served HTML outside <script> blocks, so JavaScript is never touched.
_SCRIPT_BLOCK = re.compile(r"(<script\b.*?</script>)", re.S | re.I)
_DOCS_LINK = re.compile(r'href="https?://(?:docs\.|www\.)?ctfd\.io[^"]*"', re.I)
_PLATFORM_NAME = re.compile(r"\bCTFd\b(?![.\w])")


def scrub_platform_name(html):
    parts = _SCRIPT_BLOCK.split(html)
    for i in range(0, len(parts), 2):
        parts[i] = _PLATFORM_NAME.sub("CyberPaw", _DOCS_LINK.sub('href="#"', parts[i]))
    return "".join(parts)


class CyberpawChallengeMeta(db.Model):
    __tablename__ = "cyberpaw_challenge_meta"
    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    difficulty = db.Column(db.Integer, nullable=False)


def parse_difficulty(value):
    """Return 1-5, or None to clear. Aborts with 400 on anything else."""
    if value in (None, "", 0, "0"):
        return None
    try:
        level = int(value)
    except (TypeError, ValueError):
        abort(400)
    if not 1 <= level <= 5:
        abort(400)
    return level


def files_version(*dirs):
    """Short hash of every file under dirs. Added as ?v= to CyberPaw script and style links, so
    Cloudflare's cache (4 hours) is skipped right after a deploy."""
    digest = hashlib.sha1()
    for base in dirs:
        for folder, _, names in sorted(os.walk(base)):
            for name in sorted(names):
                with open(os.path.join(folder, name), "rb") as f:
                    digest.update(f.read())
    return digest.hexdigest()[:10]


# Pages an account that hasn't confirmed its email can still use.
UNCONFIRMED_ALLOWED = {
    "auth.confirm", "auth.logout", "views.static_html", "views.themes", "views.themes_beta",
    "views.files", "views.healthcheck", "views.robots", "static",
}


def default_website(mapper, connection, user):
    if not user.website:
        user.website = DEFAULT_WEBSITE


def load(app):
    app.db.create_all()
    from .email import install as install_html_email

    install_html_email()
    install_profiles(app)
    install_first_paw(app)
    event.listen(Users, "before_insert", default_website, propagate=True)
    bp = Blueprint("cyberpaw", __name__)

    @app.after_request
    def remove_platform_name(response):
        if response.mimetype == "text/html" and not response.direct_passthrough:
            response.set_data(scrub_platform_name(response.get_data(as_text=True)))
        return response

    # One email at signup: the confirm link. No second "registered" email after confirming.
    platform_email.successful_registration_notification = lambda addr: None

    @app.before_request
    def unconfirmed_lockout():
        if request.endpoint in UNCONFIRMED_ALLOWED or not get_config("verify_emails") or not authed():
            return None
        user = get_current_user()
        if user is None or user.verified or is_admin():
            return None
        if request.path.startswith("/api/"):
            abort(403, description="Confirm your email address first")
        return redirect(url_for("auth.confirm"))

    @app.before_request
    def confirm_only_when_logged_in():
        """Confirm links work only for the logged-in owner of the account (see module docstring)."""
        token = (request.view_args or {}).get("data")
        if request.endpoint != "auth.confirm" or request.method != "GET" or not token:
            return None
        try:
            email = verify_email_confirm_token(token)
        except UserConfirmTokenInvalidException:
            return None  # the platform shows "link is invalid"
        user = get_current_user() if authed() else None
        if user is None:
            return render_template("confirm_login.html", next_url=request.path)
        if user.email.lower() != email.lower():
            return render_template("confirm_login.html", wrong_account=True)
        return None

    @app.before_request
    def disable_api_tokens():
        if request.path.rstrip("/").startswith("/api/v1/tokens"):
            abort(404)
        if request.headers.get("Authorization"):
            abort(403, description="API access tokens are disabled on this site")

    @bp.route("/plugins/cyberpaw/api/difficulty", methods=["GET"])
    @check_challenge_visibility
    @during_ctf_time_only
    @require_verified_emails
    def list_difficulty():
        query = db.session.query(
            CyberpawChallengeMeta.challenge_id, CyberpawChallengeMeta.difficulty
        ).join(Challenges, Challenges.id == CyberpawChallengeMeta.challenge_id)
        if not is_admin():
            query = query.filter(Challenges.state == "visible")
        return jsonify(success=True, data={str(cid): level for cid, level in query})

    @bp.route("/plugins/cyberpaw/api/first-paws", methods=["GET"])
    @check_score_visibility
    def first_paws():
        """Visible challenges a player solved first ("First Paw"). ?user_id=N, default: you."""
        user_id = request.args.get("user_id", type=int)
        if user_id is None:
            user = get_current_user()
            if user is None:
                abort(404)
            user_id = user.id
        mine = [
            {"id": cid, "name": name, "category": category}
            for cid, (solver_id, name, category) in first_solvers().items()
            if solver_id == user_id
        ]
        return jsonify(success=True, data=mine)

    @bp.route("/plugins/cyberpaw/api/difficulty/<int:challenge_id>", methods=["PUT"])
    @admins_only
    def set_difficulty(challenge_id):
        Challenges.query.filter_by(id=challenge_id).first_or_404()
        level = parse_difficulty((request.get_json(silent=True) or {}).get("difficulty"))
        meta = CyberpawChallengeMeta.query.filter_by(challenge_id=challenge_id).first()
        if level is None:
            if meta is not None:
                db.session.delete(meta)
        elif meta is None:
            db.session.add(CyberpawChallengeMeta(challenge_id=challenge_id, difficulty=level))
        else:
            meta.difficulty = level
        db.session.commit()
        return jsonify(success=True, data={"difficulty": level})

    app.register_blueprint(bp)

    from .admin_pages import admin_pages

    app.register_blueprint(admin_pages)
    # CyberPaw admin layout: own name, favicon, footer and a short menu.
    with open(os.path.join(HERE, "templates", "admin_base.html")) as f:
        override_template("admin/base.html", f.read())
    register_plugin_assets_directory(app, base_path="/plugins/cyberpaw/assets/", admins_only=True)
    theme_static = os.path.join(app.root_path, "themes", "cyberpaw", "static")
    app.jinja_env.globals["cp_v"] = files_version(theme_static)
    admin_v = files_version(os.path.join(HERE, "assets"))
    register_admin_plugin_stylesheet(f"/plugins/cyberpaw/assets/admin.css?v={admin_v}")
    register_admin_plugin_script(f"/plugins/cyberpaw/assets/admin.js?v={admin_v}")
