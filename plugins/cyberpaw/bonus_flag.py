"""Bonus flag: an optional second flag on a challenge, worth its own points.

Tables: `cyberpaw_bonus_flag` holds the flag and its points (one per challenge). `cyberpaw_bonus_claim` records
who found it and links to the award that pays it.

Players type the bonus flag into the normal flag box. claim_attempt() runs before the platform's own attempt
code: a submission that matches the bonus flag is recorded as a claim and answered with status "bonus";
anything else is left to the platform, so wrong guesses are counted and rate limited as usual. The bonus can
be found before or after the challenge itself is solved. Players are not told which challenges have one.

The points are an award named "Bonus flag: <challenge>", so they count toward the score and show under
Awards on the profile. sync_awards() makes the awards match the claims: one per claim while the challenge is
visible and still has its bonus flag, with the current points. It runs from the same hook as First Paw
(first_paw.py). Changing or removing the bonus flag clears its claims; changing only the points keeps them.
"""
import datetime

from flask import jsonify, request

from .platform_api import (
    Awards, Challenges, Solves, authed, clear_standings, ctf_paused, ctftime, db, get_config, get_current_user,
)

AWARD_CATEGORY = "Bonus flag"
ATTEMPT_PATH = "/api/v1/challenges/attempt"


class CyberpawBonusFlag(db.Model):
    __tablename__ = "cyberpaw_bonus_flag"
    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    content = db.Column(db.String(255), nullable=False)
    points = db.Column(db.Integer, nullable=False)


class CyberpawBonusClaim(db.Model):
    __tablename__ = "cyberpaw_bonus_claim"
    __table_args__ = (db.UniqueConstraint("challenge_id", "user_id"),)
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    award_id = db.Column(db.Integer, db.ForeignKey("awards.id", ondelete="SET NULL"))


def set_bonus(challenge_id, content, points):
    """Set the challenge's bonus flag, or remove it when content is None. The caller commits."""
    row = CyberpawBonusFlag.query.filter_by(challenge_id=challenge_id).first()
    if row is not None and row.content != content:
        # A different flag (or none): earlier finds no longer count.
        CyberpawBonusClaim.query.filter_by(challenge_id=challenge_id).delete(synchronize_session=False)
    if content is None:
        if row is not None:
            db.session.delete(row)
    elif row is None:
        db.session.add(CyberpawBonusFlag(challenge_id=challenge_id, content=content, points=points))
    else:
        row.content = content
        row.points = points


def prerequisites_met(challenge, user):
    wanted = set((challenge.requirements or {}).get("prerequisites", []))
    if not wanted:
        return True
    existing = {cid for (cid,) in db.session.query(Challenges.id)}
    solved = {cid for (cid,) in db.session.query(Solves.challenge_id).filter_by(user_id=user.id)}
    return solved >= (wanted & existing)


def claim_attempt():
    if request.method != "POST" or request.path.rstrip("/") != ATTEMPT_PATH:
        return None
    # Admin previews and API tokens (turned off on this site) are left to the platform.
    if request.args.get("preview") or request.headers.get("Authorization"):
        return None
    data = request.get_json(silent=True) if request.is_json else request.form
    if not hasattr(data, "get"):
        return None
    try:
        challenge_id = int(data.get("challenge_id"))
    except (TypeError, ValueError):
        return None
    bonus = CyberpawBonusFlag.query.filter_by(challenge_id=challenge_id).first()
    if bonus is None or str(data.get("submission") or "").strip() != bonus.content:
        return None

    # The same checks the platform makes before it accepts a flag. If one fails, the platform answers.
    user = get_current_user() if authed() else None
    if user is None or not ctftime() or ctf_paused():
        return None
    if get_config("verify_emails") and not user.verified:
        return None
    challenge = Challenges.query.filter_by(id=challenge_id).first()
    if challenge is None or challenge.state != "visible" or not prerequisites_met(challenge, user):
        return None

    message = f"Bonus flag found! +{bonus.points} points"
    if CyberpawBonusClaim.query.filter_by(challenge_id=challenge_id, user_id=user.id).first():
        message = "You already found this bonus flag."
    else:
        db.session.add(CyberpawBonusClaim(challenge_id=challenge_id, user_id=user.id))
        try:
            db.session.commit()
        except Exception:
            # The same player sent it twice at the same moment (unique challenge and user); the first stands.
            db.session.rollback()
            message = "You already found this bonus flag."
    # The award is added by sync_awards(), which runs after this request (first_paw.py).
    return jsonify(success=True, data={"status": "bonus", "message": message})


def sync_awards():
    awards = {a.id: a for a in Awards.query.filter_by(category=AWARD_CATEGORY)}
    paying = (
        db.session.query(CyberpawBonusClaim, CyberpawBonusFlag.points, Challenges.name)
        .join(CyberpawBonusFlag, CyberpawBonusFlag.challenge_id == CyberpawBonusClaim.challenge_id)
        .join(Challenges, Challenges.id == CyberpawBonusClaim.challenge_id)
        .filter(Challenges.state == "visible")
    )
    changed = False
    for claim, points, name in paying:
        title = f"Bonus flag: {name}"[:80]
        award = awards.pop(claim.award_id, None)
        if award is not None and award.user_id != claim.user_id:
            db.session.delete(award)
            award = None
        if award is None:
            award = Awards(
                user_id=claim.user_id, name=title, value=points, category=AWARD_CATEGORY, icon="crosshairs",
                description="Bonus for finding this challenge's bonus flag.", date=claim.date,
            )
            db.session.add(award)
            db.session.flush()
            claim.award_id = award.id
            changed = True
        elif award.value != points or award.name != title:
            award.value = points
            award.name = title
            changed = True
    # Awards left over: challenge hidden or deleted, bonus flag changed or removed.
    for award in awards.values():
        db.session.delete(award)
        changed = True

    if not changed:
        db.session.rollback()
        return
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return
    clear_standings()


def install(app):
    app.before_request(claim_attempt)
