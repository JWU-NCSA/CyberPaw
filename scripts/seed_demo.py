"""Fill the site with fake challenges, users and solves to check the look of the site.

Runs inside the web container (see seed-demo.sh). Everything it creates is marked so it can be
removed again: users have emails demo-NN@jwu.edu, challenges carry the tag "demo".

Usage: python seed_demo.py          add demo data (removes old demo data first)
       python seed_demo.py --wipe   remove demo data only
"""
import datetime
import io
import random
import secrets
import sys

from werkzeug.datastructures import FileStorage

from platform_api import (
    ChallengeFiles, Challenges, CyberpawChallengeMeta, DynamicChallenge, DynamicValueChallenge,
    Fails, Flags, Hints, Solves, Tags, Users, clear_challenges, clear_standings, create_app, db,
    delete_file, upload_file,
)

DEMO_TAG = "demo"
EMAIL_PREFIX = "demo-"

# name, category, points (or None for decaying score), description, hint
CHALLENGES = [
    ("Paw Print", "misc", 50, "Find the flag hidden in this sentence. It is closer than you think.", None),
    ("Caesar's Wildcat", "crypto", None, "Ymnx nx f wtyfyji rjxxflj. Decode it.", "Try every shift."),
    ("Base Camp", "crypto", 100, "`Q3liZXJQYXd7YmFzZTY0X2lzX25vdF9lbmNyeXB0aW9ufQ==`", None),
    ("Cookie Jar", "web", None, "The admin panel trusts whatever cookie you send it.", "Look at your cookies."),
    ("Robots Only", "web", 150, "Some pages ask search engines to stay away.", None),
    ("Lost Packets", "forensics", None, "We captured some traffic during the incident. Download it below.", "Follow the TCP stream."),
    ("Metadata Matters", "forensics", 200, "This photo says more than it shows.", None),
    ("Strings Attached", "rev", 100, "The flag is inside the binary. You may not even need a disassembler.", None),
    ("Overflowing Bowl", "pwn", None, "A classic buffer overflow. Connect with `nc chal.example 31337`.", "How big is the buffer?"),
    ("Secret Stash", "misc", 300, "Hidden challenge, only admins can see this one.", None),
]

# Difficulty 1-5 shown as warning triangles (cyberpaw plugin).
DIFFICULTY = {
    "Paw Print": 1, "Caesar's Wildcat": 2, "Base Camp": 1, "Cookie Jar": 3, "Robots Only": 2,
    "Lost Packets": 3, "Metadata Matters": 4, "Strings Attached": 2, "Overflowing Bowl": 5,
    "Secret Stash": 4,
}

FIRST = ["alex", "sam", "jordan", "taylor", "casey", "riley", "morgan", "jamie", "drew", "quinn",
         "avery", "rowan", "skyler", "reese", "parker"]


def wipe():
    ids = [tag.challenge_id for tag in Tags.query.filter_by(value=DEMO_TAG).all() if tag.challenge_id]
    for f in ChallengeFiles.query.filter(ChallengeFiles.challenge_id.in_(ids)).all():
        delete_file(f.id)
    # Bulk delete so the database cascade removes flags, hints, tags, solves and the rest. Deleting through
    # the ORM (session.delete) leaves those rows behind with an empty challenge_id.
    Challenges.query.filter(Challenges.id.in_(ids)).delete(synchronize_session=False)
    Users.query.filter(Users.email.like(f"{EMAIL_PREFIX}%@jwu.edu")).delete(synchronize_session=False)
    db.session.commit()


def make_challenge(name, category, points, description, hint):
    if points is None:
        chal = DynamicChallenge(
            name=name, category=category, description=description, type="dynamic",
            initial=500, minimum=100, decay=10, function="logarithmic",
        )
    else:
        chal = Challenges(name=name, category=category, description=description,
                          type="standard", value=points)
    chal.state = "hidden" if name == "Secret Stash" else "visible"
    db.session.add(chal)
    db.session.commit()

    slug = name.lower().replace(" ", "_").replace("'", "")
    db.session.add(Flags(challenge_id=chal.id, type="static", content=f"CyberPaw{{demo_{slug}}}"))
    db.session.add(Tags(challenge_id=chal.id, value=DEMO_TAG))
    db.session.add(Tags(challenge_id=chal.id, value="beginner" if (points or 0) <= 100 else "intermediate"))
    db.session.add(CyberpawChallengeMeta(challenge_id=chal.id, difficulty=DIFFICULTY[name]))
    if hint:
        db.session.add(Hints(challenge_id=chal.id, content=hint, cost=25, title="Hint"))
    db.session.commit()

    if category == "forensics" and points is None:
        data = io.BytesIO(b"This is a fake capture file for visual testing.\n")
        upload_file(file=FileStorage(stream=data, filename="capture.pcap"), type="challenge",
                    challenge_id=chal.id, location=f"demo/{slug}.pcap")
    return chal


def seed():
    rng = random.Random(2027)
    now = datetime.datetime.utcnow()

    chals = [make_challenge(*c) for c in CHALLENGES]
    visible = [c for c in chals if c.state == "visible"]

    users = []
    for i, first in enumerate(FIRST, start=1):
        user = Users(name=f"{first}_{rng.randint(10, 99)}", email=f"{EMAIL_PREFIX}{i:02d}@jwu.edu",
                     password=secrets.token_hex(16), verified=True, type="user",
                     affiliation="Johnson & Wales University")
        db.session.add(user)
        users.append(user)
    db.session.commit()

    # Stronger players solve more, so the scoreboard has a clear spread.
    for rank, user in enumerate(users):
        skill = 1 - rank / len(users)
        start = now - datetime.timedelta(hours=48)
        for chal in visible:
            if rng.random() < 0.15 + 0.75 * skill:
                when = start + datetime.timedelta(minutes=rng.randint(0, 47 * 60))
                flag = Flags.query.filter_by(challenge_id=chal.id).first().content
                db.session.add(Solves(user_id=user.id, challenge_id=chal.id, ip="127.0.0.1",
                                      provided=flag, date=when))
            elif rng.random() < 0.3:
                when = start + datetime.timedelta(minutes=rng.randint(0, 47 * 60))
                db.session.add(Fails(user_id=user.id, challenge_id=chal.id, ip="127.0.0.1",
                                     provided="CyberPaw{wrong_guess}", date=when))
    db.session.commit()

    for chal in chals:
        if chal.type == "dynamic":
            DynamicValueChallenge.calculate_value(chal)
    db.session.commit()
    return len(chals), len(users), Solves.query.count()


app = create_app()
with app.app_context():
    wipe()
    if "--wipe" in sys.argv:
        print("Removed demo data")
    else:
        print("Added %d challenges, %d users, %d solves" % seed())
    clear_challenges()
    clear_standings()
