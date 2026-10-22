"""Revoked awards: bonus awards an admin deleted, so the syncs don't add them back.

First Paw, referral and bonus flag awards are made by sync functions that run after many requests, and they
recreate any award that is missing. When an admin deletes one of these awards from a user's Awards tab, the
award is recorded here and the syncs skip it from then on. Deleting the row here gives the points back on the
next sync.

What each kind records (ref_id):
- KIND_REFERRER: the referred player's id; the award was the referrer's "Referral bonus" for them
- KIND_WELCOME: the referred player's id (same as user_id); the award was their "Welcome bonus"
- KIND_FIRST_PAW: the challenge id
- KIND_BONUS_FLAG: the challenge id

This module only imports from platform_api, so the award modules can import it without a cycle.
"""
from .platform_api import db

KIND_REFERRER = "referrer"
KIND_WELCOME = "welcome"
KIND_FIRST_PAW = "first_paw"
KIND_BONUS_FLAG = "bonus_flag"


class CyberpawRevokedAward(db.Model):
    __tablename__ = "cyberpaw_revoked_award"
    __table_args__ = (db.UniqueConstraint("kind", "user_id", "ref_id"),)
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ref_id = db.Column(db.Integer, nullable=False)


def revoked(kind):
    """{(user_id, ref_id)} for every revoked award of this kind."""
    return {
        (user_id, ref_id)
        for user_id, ref_id in db.session.query(CyberpawRevokedAward.user_id, CyberpawRevokedAward.ref_id)
        .filter_by(kind=kind)
    }


def revoke(kind, user_id, ref_id):
    """Record a revoked award, once. The caller commits."""
    if CyberpawRevokedAward.query.filter_by(kind=kind, user_id=user_id, ref_id=ref_id).first() is None:
        db.session.add(CyberpawRevokedAward(kind=kind, user_id=user_id, ref_id=ref_id))
