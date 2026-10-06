#!/bin/bash
# Send-only mail server for verification and password reset emails. Run once as root on cyberpaw-ctf.
# Delivers straight to the recipient's mail server (no relay account). Accepts mail only from this
# VM and its Docker containers, and only for JWU addresses, so it can't be used to send spam.
# Mail is DKIM-signed by OpenDKIM (selector "cyberpaw"). Safe to re-run; an existing DKIM key is kept.
# DNS records for jwucyberlab.org (Cloudflare dashboard), so JWU's mail server trusts the mail:
#   SPF:  TXT  @                         v=spf1 ip4:184.185.55.107 include:_spf.mx.cloudflare.net include:_spf.google.com ~all
#   DKIM: TXT  cyberpaw._domainkey       printed at the end of this script
set -euo pipefail

echo "postfix postfix/main_mailer_type select Internet Site" | debconf-set-selections
echo "postfix postfix/mailname string jwucyberlab.org" | debconf-set-selections
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends postfix opendkim opendkim-tools

postconf -e \
  "myhostname = mail.jwucyberlab.org" \
  "myorigin = jwucyberlab.org" \
  "mydestination =" \
  "local_transport = error:local delivery is disabled" \
  "inet_interfaces = all" \
  "inet_protocols = ipv4" \
  "mynetworks = 127.0.0.0/8 172.16.0.0/12" \
  "smtpd_client_restrictions = permit_mynetworks, reject" \
  "smtpd_relay_restrictions = permit_mynetworks, reject" \
  "smtpd_recipient_restrictions = check_recipient_access hash:/etc/postfix/allowed_recipients, reject" \
  "smtp_tls_security_level = may" \
  "smtpd_banner = \$myhostname ESMTP" \
  "always_add_missing_headers = yes" \
  "local_header_rewrite_clients = permit_mynetworks" \
  "milter_default_action = accept" \
  "smtpd_milters = inet:127.0.0.1:8891" \
  "non_smtpd_milters = inet:127.0.0.1:8891"

# jwu.edu also matches subdomains such as wildcats.jwu.edu.
printf 'jwu.edu OK\n' > /etc/postfix/allowed_recipients
postmap /etc/postfix/allowed_recipients

# DKIM signing key, made once.
KEYS=/etc/opendkim/keys
install -d -m 750 -o opendkim -g opendkim "$KEYS"
if [ ! -f "$KEYS/cyberpaw.private" ]; then
  opendkim-genkey -b 2048 -d jwucyberlab.org -s cyberpaw -D "$KEYS"
  chown opendkim:opendkim "$KEYS"/cyberpaw.*
  chmod 600 "$KEYS/cyberpaw.private"
fi
cat > /etc/opendkim.conf <<'CONF'
Syslog                yes
UMask                 007
Mode                  s
Domain                jwucyberlab.org
Selector              cyberpaw
KeyFile               /etc/opendkim/keys/cyberpaw.private
Canonicalization      relaxed/simple
OversignHeaders       From
Socket                inet:8891@127.0.0.1
# Sign mail from this VM and its Docker containers (same as Postfix mynetworks).
InternalHosts         127.0.0.0/8,172.16.0.0/12
PidFile               /run/opendkim/opendkim.pid
UserID                opendkim
CONF

systemctl enable opendkim postfix
systemctl restart opendkim postfix
echo "Postfix ready. DKIM DNS record (TXT, name cyberpaw._domainkey):"
grep -o '"[^"]*"' "$KEYS/cyberpaw.txt" | tr -d '"\n'; echo
