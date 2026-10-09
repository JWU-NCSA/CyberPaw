"""Final standing: once the competition has ended, the home page shows each player's place as a card they
can share, like the solve card in the challenge window (theme page.html and js/fun.js).

final_standing(user_id) is a template global. It returns None before the end, when players can't see
scores, or when the player isn't on the scoreboard (no points, hidden or banned).
"""
from .platform_api import Solves, ctf_ended, get_config, get_user_standings, ordinalize, scores_visible


def final_standing(user_id):
    if not user_id or not ctf_ended() or not scores_visible():
        return None
    standings = get_user_standings()
    place = next((i for i, row in enumerate(standings, 1) if row.user_id == user_id), None)
    if place is None:
        return None
    return {
        "place": place,
        "ordinal": ordinalize(place),
        "players": len(standings),
        "score": int(standings[place - 1].score),
        "solves": Solves.query.filter_by(user_id=user_id).count(),
        "end": int(get_config("end") or 0),
    }


def install(app):
    app.jinja_env.globals["cp_final_standing"] = final_standing
