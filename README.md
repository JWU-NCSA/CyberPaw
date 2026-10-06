# CyberPaw

The JWU CyberPaw capture the flag site ([jwucyberlab.org](https://jwucyberlab.org)), run by the JWU NCSA.

The site is the open-source CTFd platform (pinned Docker image `ctfd/ctfd:3.8.8`) with a CyberPaw theme and
plugin on top. This repo holds everything that is ours: the theme, the plugin, the settings script and the
server config. Upstream licenses and the list of files derived from it are in `THIRD_PARTY_NOTICES`.

## What CyberPaw adds

- JWU branding, a one-screen home page with a competition countdown, and player extras (confetti, rank chip,
  "First Paw" badges for the first solver of each challenge, easter eggs).
- Sign-up for `@jwu.edu` and `@wildcats.jwu.edu` addresses only. Players must confirm their email before
  they can use the site, and the confirm link only works while logged in to that account (so JWU's mail
  scanner, which opens every link, can't confirm accounts).
- CyberPaw-styled HTML emails sent through a send-only Postfix server on the VM.
- Player profiles: generated avatar, short bio, website, GitHub and LinkedIn.
- First solve bonus: optional extra points for each challenge's first solver (Config -> Challenges).
- A simpler admin panel: Users, Submissions, Challenges, Pages, Config. The Challenges page lists every
  challenge with a shown/hidden switch and a one-form "Add challenge" with a 1-5 difficulty and optional
  decaying points. Settings CyberPaw doesn't use are hidden.

## Repo layout

```
config/docker-compose.yml     web app, MariaDB and Redis, pinned versions
config/.env.example           names of the secrets the server needs (real values never go in git)
config/postfix-setup.sh       send-only mail server with DKIM, JWU recipients only
config/cloudflared.service    Cloudflare tunnel service (public access without open ports)
theme/cyberpaw/               site theme: templates, CSS, JavaScript
theme/assets/                 logos and favicon (uploaded by apply-config)
theme/pages/                  starting text for How to Play, Rules and Privacy Notice
theme/index.html, motd.html   home page and the rules pop-up shown once to each player
plugins/cyberpaw/             site plugin: difficulty, First Paw bonus, profiles, emails, admin pages
scripts/apply-config.sh       applies CyberPaw settings, branding and pages to the running site
scripts/seed-demo.sh          fills the site with fake challenges and players to preview it (--wipe removes them)
```

## Setting up a server

These steps assume a Debian VM with Docker and the Compose plugin installed.

1. Clone this repo to `/opt/cyberpaw/repo`.
2. Copy `config/docker-compose.yml` to `/opt/cyberpaw/`. Then copy `config/.env.example` to
   `/opt/cyberpaw/.env` and fill in the secrets: `openssl rand -hex 32` for each one. Keep `.env`
   readable by root only.
3. Start the site:
   ```
   sudo docker compose --project-directory /opt/cyberpaw up -d
   ```
   Open it and finish the platform's setup page to create the admin account.
4. Apply the CyberPaw settings and branding. Re-running this is safe:
   ```
   cd /opt/cyberpaw/repo && sudo scripts/apply-config.sh
   ```
5. Email: run `sudo config/postfix-setup.sh`. It prints a DKIM record. Add it and the SPF record from the top
   of the script to the domain's DNS.
6. Public access: install cloudflared, put the tunnel token in `/etc/cloudflared/token` (root only, never in
   git), and install `config/cloudflared.service`. The tunnel's routes are set in the Cloudflare dashboard.

The site only listens on `127.0.0.1:80`; it is reached through the tunnel.

## Making changes

- **Theme or plugin:** edit the files, copy them to `/opt/cyberpaw/repo` on the server, then restart:
  ```
  sudo docker compose --project-directory /opt/cyberpaw restart web
  ```
  Script and style links are cache-busted automatically.
- **Settings:** most settings are changed in the admin panel and stay changed. `apply-config` only fills in
  the email texts, mail server, pages and logos when they are empty. It always sets the site name, theme,
  JWU-only sign-up, email confirmation and the home page.
- **Previewing:** `sudo scripts/seed-demo.sh` adds fake data to look at, and `--wipe` removes it. Don't run
  it on the live site during a competition.
- **Updates:** nothing updates itself. Versions are pinned in `docker-compose.yml`. Change them on purpose
  and test before deploying.

Before upgrading CTFd, re-check the templates listed in `THIRD_PARTY_NOTICES` against the new version.
