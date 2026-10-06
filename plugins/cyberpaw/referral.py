"""Referrals: players invite friends with a link and both get bonus points.

Link: /register?ref=<user id>, shown on the Settings page. Opening it remembers the referrer in the session;
when that browser then creates an account, the new player is linked to the referrer (table
`cyberpaw_referral`, one row per referred player, removed with either user).

A referral counts once the new player has confirmed their email and solved at least one challenge, so empty
accounts earn nothing. Both players must not be hidden or banned. Then:
- the referrer gets an award worth REFERRER_POINTS, for at most REFERRER_CAP points in total (the earliest
  counting referrals win)
- the new player gets an award worth NEW_PLAYER_POINTS

sync_awards() makes the awards match the current referrals, like First Paw (first_paw.py). It runs after the
same requests.
"""
from flask import request, session, url_for

from .platform_api import Awards, Solves, Users, clear_standings, db, get_config, get_current_user

REFERRER_POINTS = 50
REFERRER_CAP = 300
NEW_PLAYER_POINTS = 25
AWARD_CATEGORY = "Referral"
SESSION_KEY = "cp_ref"


class CyberpawReferral(db.Model):
    __tablename__ = "cyberpaw_referral"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    referrer_award_id = db.Column(db.Integer, db.ForeignKey("awards.id", ondelete="SET NULL"))
    user_award_id = db.Column(db.Integer, db.ForeignKey("awards.id", ondelete="SET NULL"))


def max_referrals():
    return REFERRER_CAP // REFERRER_POINTS


def counting_referrals():
    """{referred user id: referrer id} for every referral that earns points, before the cap."""
    eligible = {
        uid for (uid,) in db.session.query(Users.id).filter(Users.hidden.is_(False), Users.banned.is_(False))
    }
    verify = bool(get_config("verify_emails"))
    verified = {uid for (uid,) in db.session.query(Users.id).filter(Users.verified.is_(True))}
    solved = {uid for (uid,) in db.session.query(Solves.user_id).distinct()}
    out = {}
    for row in CyberpawReferral.query.order_by(CyberpawReferral.user_id):
        uid, rid = row.user_id, row.referrer_id
        if uid in eligible and rid in eligible and uid in solved and (uid in verified or not verify):
            out[uid] = rid
    return out


def sync_awards():
    counting = counting_referrals()
    per_referrer = {}
    paid = set()  # referred players whose referrer is still under the cap
    for uid, rid in counting.items():
        if per_referrer.get(rid, 0) < max_referrals():
            per_referrer[rid] = per_referrer.get(rid, 0) + 1
            paid.add(uid)

    awards = {a.id: a for a in Awards.query.filter_by(category=AWARD_CATEGORY)}
    changed = False

    def drop(award_id):
        award = awards.pop(award_id, None)
        if award is not None:
            db.session.delete(award)
        return None

    def ensure(award_id, user_id, value, name, description):
        nonlocal changed
        award = awards.get(award_id)
        if award is not None and award.user_id == user_id:
            if award.value != value:
                award.value = value
                changed = True
            return award_id
        if award is not None:
            drop(award_id)
        award = Awards(
            user_id=user_id, name=name, value=value, category=AWARD_CATEGORY, icon="lightning",
            description=description,
        )
        db.session.add(award)
        db.session.flush()
        changed = True
        return award.id

    for row in CyberpawReferral.query.order_by(CyberpawReferral.user_id):
        if row.user_id in paid:
            row.referrer_award_id = ensure(
                row.referrer_award_id, row.referrer_id, REFERRER_POINTS, "Referral bonus",
                "Bonus for bringing a new player to CyberPaw.",
            )
        elif row.referrer_award_id is not None:
            row.referrer_award_id = drop(row.referrer_award_id)
            changed = True
        if row.user_id in counting:
            row.user_award_id = ensure(
                row.user_award_id, row.user_id, NEW_PLAYER_POINTS, "Welcome bonus",
                "Bonus for joining CyberPaw with a friend's invite link.",
            )
        elif row.user_award_id is not None:
            row.user_award_id = drop(row.user_award_id)
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


def referral_info(user_id):
    """For the Settings page: invite link, counting referrals and points earned."""
    counted = sum(1 for rid in counting_referrals().values() if rid == user_id)
    pending = CyberpawReferral.query.filter_by(referrer_id=user_id).count() - counted
    paid = min(counted, max_referrals())
    return {
        "link": url_for("auth.register", ref=user_id, _external=True),
        "counted": counted,
        "pending": pending,
        "points": paid * REFERRER_POINTS,
        "per_referral": REFERRER_POINTS,
        "cap": REFERRER_CAP,
        "new_player_points": NEW_PLAYER_POINTS,
    }


def install(app):
    app.jinja_env.globals["cp_referral"] = referral_info

    @app.before_request
    def remember_referrer():
        if request.endpoint != "auth.register" or request.method != "GET":
            return None
        ref = request.args.get("ref", type=int)
        if ref and get_current_user() is None and Users.query.filter_by(id=ref, banned=False).first():
            session[SESSION_KEY] = ref
        return None

    @app.after_request
    def link_new_player(response):
        """Registration succeeded when the POST redirects with the new player logged in."""
        if (
            request.endpoint == "auth.register"
            and request.method == "POST"
            and response.status_code in (301, 302, 303)
            and session.get(SESSION_KEY)
            and session.get("id")
        ):
            ref = session.pop(SESSION_KEY)
            uid = session["id"]
            try:
                if ref != uid and CyberpawReferral.query.get(uid) is None and Users.query.get(ref):
                    db.session.add(CyberpawReferral(user_id=uid, referrer_id=ref))
                    db.session.commit()
            except Exception:
                db.session.rollback()
                app.logger.exception("Saving referral failed")
        return response
