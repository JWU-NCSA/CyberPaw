"""Apply CyberPaw settings and branding to the running site.

Runs inside the web container (see apply-config.sh). Safe to re-run: uploads use
fixed locations, so each run overwrites the previous files instead of adding new ones.

SETTINGS are always applied. DEFAULTS, the logos, the message of the day and the Rules, How to Play and
Privacy Notice pages are only filled in when empty, so edits made in the admin panel stay. The home
page layout (index.html) is always replaced.

Usage: python apply_config.py <theme_dir>
"""
import os
import sys

from werkzeug.datastructures import FileStorage

from platform_api import (
    Configs, Pages, clear_config, clear_pages, create_app, db, set_config, sync_first_paw_awards, upload_file,
)

SETTINGS = {
    "ctf_name": "JWU CyberPaw CTF",
    # theme/cyberpaw, mounted by docker-compose.yml. Falls back to core for pages it doesn't override.
    "ctf_theme": "cyberpaw",
    # Only JWU addresses can register, and they must click the emailed link first.
    "verify_emails": True,
    "domain_whitelist": "jwu.edu,wildcats.jwu.edu",
    # English only; the language menu and fields are removed from the site.
    "default_locale": "en",
    # Registration says "you agree to the privacy policy and terms of service"; point at our pages.
    "tos_url": "/rules",
    "privacy_url": "/privacy-notice",
}

# Starting values; the admin panel can change them afterwards.
DEFAULTS = {
    # Extra points for the first solver of each challenge (Config -> Challenges, plugins/cyberpaw/first_paw.py).
    "cyberpaw_first_solve_bonus": 1,
    # Postfix on the VM (config/postfix-setup.sh), reached from the container as host.docker.internal.
    "mail_server": "host.docker.internal",
    "mail_port": 25,
    "mail_useauth": False,
    "mail_tls": False,
    "mail_ssl": False,
    "mailfrom_addr": "noreply@jwucyberlab.org",
    # Emails, sent through Postfix on the VM (config/postfix-setup.sh). {ctf_name} and {url} are filled
    # in by the platform; {url} is the confirm or reset link.
    "verification_email_subject": "Confirm your {ctf_name} account",
    "verification_email_body": (
        "Welcome to {ctf_name}!\n\n"
        "Confirm your JWU email address to activate your account:\n"
        "{url}\n\n"
        "If the link doesn't open, copy and paste it into your browser.\n"
        "If you didn't sign up, you can ignore this email.\n\n"
        "Go Wildcats!\n"
        "The CyberPaw team"
    ),
    "successful_registration_email_subject": "You're registered for {ctf_name}",
    "successful_registration_email_body": (
        "Your {ctf_name} account is active.\n\n"
        "New to CTFs? These get you started:\n"
        "How to Play: https://jwucyberlab.org/how-to-play\n"
        "Rules: https://jwucyberlab.org/rules\n\n"
        "Every flag looks like CyberPaw{...}.\n"
        "Ready? Jump in:\n"
        "https://jwucyberlab.org/challenges\n\n"
        "Good luck!\n"
        "The CyberPaw team"
    ),
    "password_reset_subject": "Reset your {ctf_name} password",
    "password_reset_body": (
        "Someone asked to reset the password for your {ctf_name} account.\n\n"
        "Choose a new password here:\n"
        "{url}\n\n"
        "If the link doesn't open, copy and paste it into your browser.\n"
        "If you didn't ask for this, ignore this email; your password stays the same.\n\n"
        "The CyberPaw team"
    ),
    "password_change_alert_subject": "Your {ctf_name} password was changed",
    "password_change_alert_body": (
        "The password for your {ctf_name} account was just changed.\n\n"
        "If this wasn't you, reset it right away:\n"
        "{url}\n\n"
        "The CyberPaw team"
    ),
    "user_creation_email_subject": "Your {ctf_name} account",
    "user_creation_email_body": (
        "An organizer made a {ctf_name} account for you at {url}\n\n"
        "Username: {name}\n"
        "Password: {password}\n\n"
        "Log in and change your password with \"Forgot your password?\" on the login page.\n\n"
        "The CyberPaw team"
    ),
    # Easter egg for players who check robots.txt.
    "robots_txt": (
        "User-agent: *\n"
        "Disallow: /admin\n"
        "\n"
        "# Hey there, curious wildcat. 🐾\n"
        "# Robots aren't allowed in /admin, and judging by the fact you're reading this,\n"
        "# you're not a robot either. Sadly there are no flags in this file. Keep hunting!\n"
    ),
}

theme_dir = sys.argv[1]


def set_if_missing(key, value):
    row = Configs.query.filter_by(key=key).first()
    if row is None or row.value in (None, ""):
        set_config(key, value)


def upload(name):
    """Upload theme/assets/<name> to a fixed location and return the public URL path."""
    with open(os.path.join(theme_dir, "assets", name), "rb") as f:
        row = upload_file(file=FileStorage(stream=f, filename=name), location=f"cyberpaw/{name}")
    return row.location


def read(name, logo_url):
    with open(os.path.join(theme_dir, name)) as f:
        return f.read().replace("{{LOGO_URL}}", logo_url)


app = create_app()
with app.app_context():
    logo = upload("cyberpaw-logo.png")
    shield = upload("jwu-shield.png")
    icon = upload("favicon.png")
    logo_url = f"/files/{logo}"

    for key, value in SETTINGS.items():
        set_config(key, value)
    for key, value in DEFAULTS.items():
        set_if_missing(key, value)
    set_if_missing("ctf_logo", shield)
    set_if_missing("ctf_small_icon", icon)
    set_if_missing("ctf_banner", logo)
    # Rules and How to Play show in the navbar; Privacy is linked from Rules and registration.
    for route, title, hidden in (
        ("how-to-play", "How to Play", False),
        ("rules", "Rules", False),
        ("privacy-notice", "Privacy Notice", True),
    ):
        if Pages.query.filter_by(route=route).first() is None:
            db.session.add(Pages(
                route=route, title=title, content=read(f"pages/{route}.md", logo_url), format="markdown",
                draft=False, hidden=hidden, auth_required=False,
            ))

    # Message of the day: shown once to each player (js/fun.js) until its version changes.
    set_if_missing("theme_footer", read("motd.html", logo_url))

    index = Pages.query.filter_by(route="index").first()
    if index is None:
        index = Pages(title=SETTINGS["ctf_name"], route="index", draft=False)
        db.session.add(index)
    index.content = read("index.html", logo_url)
    index.format = "html"
    db.session.commit()

    clear_config()
    clear_pages()
    # Give (or update) First Paw bonus awards for the current bonus setting.
    sync_first_paw_awards()
    print("Applied CyberPaw config")
