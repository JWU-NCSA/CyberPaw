"""Player profiles: generated avatar, short bio and GitHub / LinkedIn links.

- table `cyberpaw_profile` (one row per player who changed something, removed with the user)
- GET  /plugins/cyberpaw/avatar/<user_id>.svg   generated avatar (GitHub-style 5x5 pattern). Nothing is
  uploaded, so there are no player images to store, scan or serve.
- GET  /plugins/cyberpaw/api/profile            the logged-in player's profile
- PATCH /plugins/cyberpaw/api/profile           {"bio", "github", "linkedin", "new_avatar": true}
- Jinja helpers for the theme: cp_profile(user_id), cp_avatar_url(user_id), and the cp_link_text filter
  ("https://www.example.com/" shows as "example.com").
"""
import hashlib
import re

from flask import Blueprint, abort, jsonify, request, session
from markupsafe import escape

from .platform_api import authed, db, get_current_user

BIO_MAX = 200
GITHUB = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
LINKEDIN = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_%-]{1,99}$")


class CyberpawProfile(db.Model):
    __tablename__ = "cyberpaw_profile"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    bio = db.Column(db.String(BIO_MAX), nullable=False, default="")
    github = db.Column(db.String(39), nullable=False, default="")
    linkedin = db.Column(db.String(100), nullable=False, default="")
    avatar_seed = db.Column(db.Integer, nullable=False, default=0)


def get_profile(user_id):
    row = CyberpawProfile.query.filter_by(user_id=user_id).first()
    if row is None:
        return {"bio": "", "github": "", "linkedin": "", "avatar_seed": 0}
    return {"bio": row.bio, "github": row.github, "linkedin": row.linkedin, "avatar_seed": row.avatar_seed}


def avatar_url(user_id):
    return f"/plugins/cyberpaw/avatar/{int(user_id)}.svg?s={get_profile(user_id)['avatar_seed']}"


def link_text(url):
    text = re.sub(r"^https?://", "", url or "", flags=re.I)
    text = re.sub(r"^www\.", "", text, flags=re.I)
    return text.rstrip("/")


def identicon(user_id, seed):
    """5x5 left-right mirrored pattern in one color, like GitHub's default avatars. The margin keeps the
    pattern inside the round frame."""
    digest = hashlib.sha256(f"cyberpaw:{user_id}:{seed}".encode()).digest()
    hue = int.from_bytes(digest[0:2], "big") % 360
    color = f"hsl({hue}, {55 + digest[2] % 20}%, {45 + digest[3] % 15}%)"
    cells = []
    for row in range(5):
        for col in range(3):
            if digest[4 + row * 3 + col] % 2 == 0:
                for x in {col, 4 - col}:
                    cells.append(f'<rect x="{x + 1.5}" y="{row + 1.5}" width="1" height="1"/>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8" shape-rendering="crispEdges">'
        '<rect width="8" height="8" fill="#f0f0f0"/>'
        f'<g fill="{color}">{"".join(cells)}</g></svg>'
    )


def clean_profile(data):
    """Validated fields from a PATCH body. Aborts with 400 and a message on bad input."""
    out = {}

    def fail(message):
        response = jsonify(success=False, errors={"profile": [message]})
        response.status_code = 400
        abort(response)

    if "bio" in data:
        bio = " ".join(str(data["bio"] or "").split())
        if len(bio) > BIO_MAX:
            fail(f"Bio is limited to {BIO_MAX} characters.")
        out["bio"] = bio
    if "github" in data:
        github = re.sub(r"^(https?://)?(www\.)?github\.com/", "", str(data["github"] or "").strip(), flags=re.I).strip("/@")
        if github and not GITHUB.match(github):
            fail("GitHub username can only have letters, numbers and dashes.")
        out["github"] = github
    if "linkedin" in data:
        linkedin = re.sub(r"^(https?://)?([a-z]+\.)?linkedin\.com/in/", "", str(data["linkedin"] or "").strip(), flags=re.I).strip("/")
        if linkedin and not LINKEDIN.match(linkedin):
            fail("LinkedIn: use the part after linkedin.com/in/.")
        out["linkedin"] = linkedin
    return out


profile_bp = Blueprint("cyberpaw_profile", __name__)


@profile_bp.route("/plugins/cyberpaw/avatar/<int:user_id>.svg")
def avatar(user_id):
    svg = identicon(user_id, get_profile(user_id)["avatar_seed"])
    # The URL changes with the seed, so it can be cached for a long time.
    return svg, 200, {"Content-Type": "image/svg+xml", "Cache-Control": "public, max-age=604800"}


@profile_bp.route("/plugins/cyberpaw/api/profile", methods=["GET", "PATCH"])
def my_profile():
    if not authed():
        abort(403)
    user = get_current_user()
    if request.method == "PATCH":
        if request.headers.get("CSRF-Token") != session.get("nonce"):
            abort(403)
        data = request.get_json(silent=True) or {}
        fields = clean_profile(data)
        row = CyberpawProfile.query.filter_by(user_id=user.id).first()
        if row is None:
            row = CyberpawProfile(user_id=user.id, bio="", github="", linkedin="", avatar_seed=0)
            db.session.add(row)
        for key, value in fields.items():
            setattr(row, key, value)
        if data.get("new_avatar"):
            row.avatar_seed = (row.avatar_seed or 0) + 1
        db.session.commit()
    return jsonify(success=True, data={**get_profile(user.id), "avatar_url": avatar_url(user.id)})


def install(app):
    app.register_blueprint(profile_bp)
    app.jinja_env.globals["cp_profile"] = get_profile
    app.jinja_env.globals["cp_avatar_url"] = avatar_url
    app.jinja_env.filters["cp_link_text"] = lambda url: escape(link_text(url))
