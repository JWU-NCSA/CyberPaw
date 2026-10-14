import datetime

from flask import request

from .platform_api import Challenges, clear_challenges, clear_standings, db


class CyberpawChallengeRelease(db.Model):
    __tablename__ = "cyberpaw_challenge_release"
    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    release_at = db.Column(db.DateTime, nullable=False) #UTC



Release = CyberpawChallengeRelease


def release_due():
    now = datetime.datetime.utcnow()
    due = [r.challenge_id for r in Release.query.filter(Release.release_at <= now)]
    if not due:
        return
    Challenges.query.filter(Challenges.id.in_(due)).update({"state": "visible"}, synchronize_session=False)
    Release.query.filter(Release.challenge_id.in_(due)).delete(synchronize_session=False)
    db.session.commit()
    clear_challenges()
    clear_standings()



# Requests that show challenges to players
RELEASE_PREFIXES = ("/challenges", "/api/v1/challenges", "/plugins/cyberpaw/api")


def install(app):
    @app.before_request
    def release_scheduled_challenges():
        if request.path.startswith(RELEASE_PREFIXES):
            try:
                release_due()
            except Exception:
                db.session.rollback()
                app.logger.exception("Scheduled challenge release failed")
        return None
    