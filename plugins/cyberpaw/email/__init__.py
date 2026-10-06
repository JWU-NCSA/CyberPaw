"""CyberPaw-styled HTML emails.

The platform sends plain-text emails with long confirm and reset links. This replaces its SMTP sender
so every email also has an HTML version: the CyberPaw logo (attached inline, so Outlook shows it
without "download pictures"), a heading, and buttons instead of raw links. The plain text stays as the
fallback part. Email texts themselves are set in scripts/apply_config.py.

How text becomes HTML:
- a line that is only a link becomes a big button (label picked from the subject)
- a line like "How to Play: https://..." becomes a link labelled "How to Play"
- "copy and paste" hints and the sign-off are left out (the layout has its own sign-off)
"""
import html
import os
import re
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from socket import timeout
from string import Template

from ..platform_api import SMTPEmailProvider, get_config, get_smtp

HERE = os.path.dirname(__file__)
SITE_URL = "https://jwucyberlab.org"

URL = re.compile(r"https?://\S+")
LABELLED_LINK = re.compile(r"^([^:]{1,30}):\s*(https?://\S+)$")
SKIP_LINES = re.compile(r"copy and paste|^the cyberpaw team$|^go wildcats!?$", re.I)

P_STYLE = "margin:0 0 14px; font-size:15px; line-height:1.6; color:#1f2a37;"
BUTTON = (
    '<table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:22px auto;">'
    '<tr><td style="border-radius:6px; background:#2664A2;">'
    '<a href="{url}" style="display:inline-block; padding:13px 30px; font-size:16px; font-weight:bold; '
    'color:#ffffff; text-decoration:none; border-radius:6px;">{label}</a>'
    "</td></tr></table>"
)
LINK = '<a href="{url}" style="color:#2664A2; font-weight:bold;">{label}</a>'

with open(os.path.join(HERE, "layout.html")) as f:
    LAYOUT = Template(f.read())
with open(os.path.join(HERE, "logo.png"), "rb") as f:
    LOGO = f.read()


def button_label(subject):
    s = subject.lower()
    if "confirm" in s:
        return "Confirm my account"
    if "reset" in s or "password" in s:
        return "Reset my password"
    return "Go to CyberPaw"


def render_line(line, subject):
    """Return ("p", html) for text that joins a paragraph, or ("block", html) for a button."""
    if URL.fullmatch(line):
        url = html.escape(line, quote=True)
        return "block", BUTTON.format(url=url, label=button_label(subject))
    labelled = LABELLED_LINK.match(line)
    if labelled:
        label, url = labelled.groups()
        return "p", "&#10140; " + LINK.format(url=html.escape(url, quote=True), label=html.escape(label))
    out, last = [], 0
    for m in URL.finditer(line):
        out.append(html.escape(line[last:m.start()]))
        url = m.group(0).rstrip(".,")
        out.append(LINK.format(url=html.escape(url, quote=True), label=html.escape(url.split("://", 1)[1].rstrip("/"))))
        last = m.start() + len(url)
    out.append(html.escape(line[last:]))
    return "p", "".join(out)


def to_html(text, subject, logo_cid):
    parts = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in paragraph.splitlines() if l.strip() and not SKIP_LINES.search(l.strip())]
        current = []
        for line in lines:
            kind, chunk = render_line(line, subject)
            if kind == "block":
                if current:
                    parts.append(f'<p style="{P_STYLE}">{"<br>".join(current)}</p>')
                    current = []
                parts.append(chunk)
            else:
                current.append(chunk)
        if current:
            parts.append(f'<p style="{P_STYLE}">{"<br>".join(current)}</p>')
    return LAYOUT.substitute(
        subject=html.escape(subject), body="\n".join(parts), logo_cid=logo_cid, site_url=SITE_URL
    )


def build_message(addr, text, subject, mailfrom):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mailfrom
    msg["To"] = addr
    msg.set_content(text)
    cid = make_msgid(domain="jwucyberlab.org")
    msg.add_alternative(to_html(text, subject, cid[1:-1]), subtype="html")
    msg.get_payload()[1].add_related(LOGO, "image", "png", cid=cid, filename="cyberpaw.png")
    return msg


def sendmail(addr, text, subject):
    """Same results as the platform's SMTP sender, with an HTML part added. Uses the mail server in
    Config -> Email (set by scripts/apply_config.py: Postfix on the VM)."""
    mailfrom = formataddr((get_config("ctf_name"), get_config("mailfrom_addr")))
    settings = {k: get_config(f"mail_{k}") for k in ("server", "port", "username", "password", "tls", "ssl", "useauth")}
    if not settings["server"]:
        return False, "No mail server set in Config -> Email"
    data = {"host": settings["server"], "port": int(settings["port"])}
    for key, name in (("username", "username"), ("password", "password"), ("tls", "TLS"), ("ssl", "SSL"), ("useauth", "auth")):
        if settings[key]:
            data[name] = settings[key]
    try:
        smtp = get_smtp(**data)
        smtp.send_message(build_message(addr, text, subject, mailfrom))
        smtp.quit()
        return True, "Email sent"
    except smtplib.SMTPException as e:
        return False, str(e)
    except timeout:
        return False, "SMTP server connection timed out"
    except Exception as e:
        return False, str(e)


def install():
    SMTPEmailProvider.sendmail = staticmethod(sendmail)
