"""
Only JWU student emails in the J-number format can sign up, like J03421345@jwu.edu.

JWU gives every student 3 addresses for the same mailbox: one with their J number and one with their
name. Accepting only the J-number one means each student has exactly one address they can sign up with,
and the platform already refuses an email that is taken. This stops:
- one person making several accounts (for example to collect referral points from themselves)
- a second account used to try out flags while the main account keeps a clean record

Rejected: the name format, J numbers without exactly 8 digits, subdomains (@wildcats.jwu.edu) and any
other domain.

Checked on the register form and when a player changes their email through the API (the Settings page
shows the email read-only, but the API would still accept a new one). Admins can still set any email.

This only checks the format. Email confirmation is what proves the player owns the address.
"""

import re

from flask import jsonify, render_template, request

from .platform_api import is_admin

J_NUMBER_EMAIL = re.compile(r"^j\d{8}@jwu\.edu$", re.I)
EMAIL_ERROR = "Use your JWU student email with your J number (ex. J03421345@jwu.edu)"



def valid_email(email):
    return bool(J_NUMBER_EMAIL.match((email or "").strip()))

def install(app):
    @app.before_request
    def j_number_email_only():
            if request.endpoint == "auth.register" and request.method == "POST":
                 email = request.form.get("email", "")
                 if not valid_email(email):
                      return render_template(
                           "register.html",
                           errors=[EMAIL_ERROR],
                           name=request.form.get("name", ""),
                           email=email,
                      )
            elif request.path.rstrip("/") == "/api/v1/users/me" and request.method == "PATCH" and not is_admin():
                 data = request.get_json(silent=True) or {}
                 if "email" in data and not valid_email(data["email"]):
                      return jsonify({"success": False, "errors": {"email": [EMAIL_ERROR]}}), 400
            return None

    