"""First Paw: the first player to solve a challenge, and the optional bonus points for it.

Who counts: the earliest solve of each visible challenge by a player who isn't hidden or banned (ties go to the
solve recorded first). The badges on the challenge list and profiles and the bonus use the same rule.

Bonus: setting `cyberpaw_first_solve_bonus` (Config -> Challenges, 0 = off). Each First Paw gets an award worth
that many points, named "First Paw: <challenge>", so it counts toward the score and shows under Awards on the
profile. The table `cyberpaw_first_paw_award` links each bonus award to its challenge.

sync_awards() makes the awards match the current First Paws: it adds missing ones, moves them when the first
solver changes (solve deleted, player hidden or banned, challenge hidden), updates the value when the setting
changes, and removes them all when the bonus is off. It runs after any request that could change any of that.
"""
from flask import request

from .platform_api import Awards, Challenges, Solves, Users, clear_standings, db, get_config

SETTING = "cyberpaw_first_solve_bonus"
AWARD_CATEGORY = "First Paw"


class CyberpawFirstPawAward(db.Model):
    __tablename__ = "cyberpaw_first_paw_award"
    award_id = db.Column(db.Integer, db.ForeignKey("awards.id", ondelete="CASCADE"), primary_key=True)
    challenge_id = db.Column(db.Integer, nullable=False, unique=True)


def first_solvers():
    """{challenge_id: (user_id, challenge name, category)} for every visible challenge with a solve."""
    rows = (
        db.session.query(Solves.challenge_id, Solves.user_id, Challenges.name, Challenges.category)
        .join(Users, Users.id == Solves.user_id)
        .join(Challenges, Challenges.id == Solves.challenge_id)
        .filter(Users.hidden.is_(False), Users.banned.is_(False), Challenges.state == "visible")
        .order_by(Solves.challenge_id, Solves.date.asc(), Solves.id.asc())
    )
    firsts = {}
    for challenge_id, user_id, name, category in rows:
        firsts.setdefault(challenge_id, (user_id, name, category))
    return firsts


def bonus_points():
    try:
        return max(0, int(get_config(SETTING) or 0))
    except (TypeError, ValueError):
        return 0


def sync_awards():
    points = bonus_points()
    wanted = first_solvers() if points else {}
    changed = False
    links = {
        link.challenge_id: (link, award)
        for link, award in db.session.query(CyberpawFirstPawAward, Awards).join(
            Awards, Awards.id == CyberpawFirstPawAward.award_id
        )
    }
    for challenge_id, (link, award) in links.items():
        first = wanted.get(challenge_id)
        if first is None or first[0] != award.user_id:
            db.session.delete(link)
            db.session.flush()
            db.session.delete(award)
            changed = True
        elif award.value != points or award.name != f"First Paw: {first[1]}"[:80]:
            award.value = points
            award.name = f"First Paw: {first[1]}"[:80]
            changed = True
    db.session.flush()
    for challenge_id, (user_id, name, _category) in wanted.items():
        existing = links.get(challenge_id)
        if existing and existing[1].user_id == user_id:
            continue
        award = Awards(
            user_id=user_id, name=f"First Paw: {name}"[:80], value=points, category=AWARD_CATEGORY,
            icon="crown", description="Bonus for being the first to solve this challenge.",
        )
        db.session.add(award)
        db.session.flush()
        db.session.add(CyberpawFirstPawAward(award_id=award.id, challenge_id=challenge_id))
        changed = True
    if not changed:
        db.session.rollback()
        return
    try:
        db.session.commit()
    except Exception:
        # Another request synced at the same moment (unique challenge_id); its result stands.
        db.session.rollback()
        return
    clear_standings()


# Requests after which the First Paws or the bonus can have changed.
SYNC_PREFIXES = (
    "/api/v1/challenges",  # attempts, challenge edits (hide, delete)
    "/api/v1/submissions",  # admin deletes or marks submissions
    "/api/v1/users",  # hide, ban, delete
    "/api/v1/configs",  # bonus setting
    "/api/v1/awards",
    "/admin/cyberpaw",  # visible/hidden toggle, new challenges
    "/admin/reset", "/admin/import",
)


def install(app):
    @app.after_request
    def sync_after_change(response):
        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and response.status_code < 400
            and request.path.startswith(SYNC_PREFIXES)
        ):
            try:
                sync_awards()
            except Exception:
                db.session.rollback()
                app.logger.exception("First Paw bonus sync failed")
        return response
