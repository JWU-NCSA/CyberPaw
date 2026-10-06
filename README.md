# CyberPaw: Standard Operating Procedure

How to go from nothing to a fully working CyberPaw site ([jwucyberlab.org](https://jwucyberlab.org)) on a new
virtual machine. Follow the steps in order. Every command is meant to be copied exactly. Lines in `<ANGLE
BRACKETS>` are values you fill in.

## 0. What you need before you start

| Item | Where it comes from |
|---|---|
| Admin login to the Proxmox host (web UI and root shell) | Club officers |
| Your SSH public key (`~/.ssh/id_ed25519.pub`) | Make one with `ssh-keygen -t ed25519` if you don't have one |
| Tailscale account in the club tailnet | Club officers |
| Cloudflare tunnel token for `jwucyberlab.org` | Cloudflare dashboard -> Zero Trust -> Networks -> Tunnels -> the CyberPaw tunnel -> Configure. Treat it like a password |
| Access to the `jwucyberlab.org` DNS records in Cloudflare | Club officers (needed for email, step 9) |
| Read access to this repo | github.com/JWU-NCSA/CyberPaw |

The tunnel already sends `jwucyberlab.org` to `http://localhost:80` on whichever machine runs it. You don't
need to change any tunnel routes.

**Only one machine may run the tunnel at a time.** If an older CyberPaw VM is still running cloudflared,
stop it there first (`sudo systemctl disable --now cloudflared`). Otherwise visitors are split between the
old and new site.

## 1. Create the VM (on the Proxmox host)

Open a root shell on the Proxmox host. These commands create a Debian 13 VM with 2 cores, 4 GB RAM and a
32 GB disk. Pick a free VM ID (check the Proxmox web UI) and use it for `<ID>` in every command.

```
cd /var/lib/vz/template
wget https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2

qm create <ID> --name cyberpaw-ctf --ostype l26 --cores 2 --cpu host --memory 4096 \
  --net0 virtio,bridge=vmbr0,firewall=1 --scsihw virtio-scsi-single --agent enabled=1 \
  --serial0 socket --vga serial0
qm importdisk <ID> debian-13-genericcloud-amd64.qcow2 local-lvm
qm set <ID> --scsi0 local-lvm:vm-<ID>-disk-0,discard=on,iothread=1 --boot order=scsi0
qm resize <ID> scsi0 32G
qm set <ID> --ide2 local-lvm:cloudinit --ciuser debian --ipconfig0 ip=dhcp
```

Copy your SSH public key to the Proxmox host (for example to `/root/mykey.pub`), then:

```
qm set <ID> --sshkeys /root/mykey.pub
qm start <ID>
```

Wait about a minute. Find the VM's address in the Proxmox web UI (VM -> Summary -> IPs), then from a machine
on the same network:

```
ssh debian@<VM IP>
```

All the remaining steps run **on the VM** as the `debian` user, with `sudo` where shown.

## 2. Base setup and no automatic updates

Nothing on the CyberPaw servers updates itself. Versions only change when an admin changes them on purpose.

```
sudo hostnamectl set-hostname cyberpaw-ctf
sudo apt-get update
sudo apt-get -y upgrade
sudo apt-get install -y ca-certificates curl git

# Turn off automatic package updates.
sudo systemctl disable --now apt-daily.timer apt-daily-upgrade.timer
printf 'APT::Periodic::Update-Package-Lists "0";\nAPT::Periodic::Unattended-Upgrade "0";\n' | sudo tee /etc/apt/apt.conf.d/20auto-upgrades
```

## 3. Tailscale (admin access)

All admin access to the VM goes over Tailscale. Nothing on the VM is opened to the internet.

```
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Open the link it prints and sign in to the club tailnet. Then check the VM's Tailscale address:

```
tailscale ip -4
```

From now on, connect with `ssh debian@<Tailscale IP>` instead of the local network address.

## 4. Docker

This uses Docker's official Debian repository:

```
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian trixie stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo docker compose version
```

## 5. Get the code and the secrets in place

The repo lives at `/opt/cyberpaw/repo`. The live configuration (`docker-compose.yml` and `.env`) lives one
folder up, in `/opt/cyberpaw`. Everything is owned by root.

```
sudo mkdir -p /opt/cyberpaw
sudo git clone https://github.com/JWU-NCSA/CyberPaw.git /opt/cyberpaw/repo
sudo cp /opt/cyberpaw/repo/config/docker-compose.yml /opt/cyberpaw/
sudo cp /opt/cyberpaw/repo/config/.env.example /opt/cyberpaw/.env
sudo chmod 600 /opt/cyberpaw/.env
sudo chmod 750 /opt/cyberpaw
```

Fill in the three secrets. Run this three times and paste one value into each empty line of `.env`
(`SECRET_KEY`, `DB_PASSWORD`, `DB_ROOT_PASSWORD`):

```
openssl rand -hex 32
sudo nano /opt/cyberpaw/.env
```

Leave `REPO_DIR=/opt/cyberpaw/repo` and `WORKERS=2` as they are. Never commit `.env` or paste it anywhere.

## 6. Start the site

```
sudo docker compose --project-directory /opt/cyberpaw up -d
sudo docker compose --project-directory /opt/cyberpaw ps
```

The `db` service should say `healthy` and `web` should say `Up`. The first start takes a minute. Then:

```
curl -s http://127.0.0.1/healthcheck
```

It should print `OK`. The site only listens on the VM itself (`127.0.0.1:80`), so it is not public yet.

## 7. First-time setup page (create the admin account)

Do this **before** the tunnel is turned on (step 10), so nobody else can reach the setup page first.

On **your own computer**, forward the site through SSH:

```
ssh -L 8080:127.0.0.1:80 debian@<Tailscale IP>
```

Leave that window open and browse to `http://localhost:8080`. Fill in the setup page:

- **General:** Event name `JWU CyberPaw CTF`.
- **Mode:** `User Mode` (CyberPaw is individual players, never teams).
- **Administration:** the admin username, email and a strong password. Store them in the club's password
  manager.
- **Settings, Style, Date & Time, Integrations:** leave as they are and click **Finish**. The next step sets
  all of it.

## 8. Apply the CyberPaw settings

Back on the VM:

```
cd /opt/cyberpaw/repo
sudo bash scripts/apply-config.sh
```

It must end with `Applied CyberPaw config`. This sets:
- the theme, logos and branding
- JWU-only sign-up and email confirmation
- the How to Play, Rules and Privacy Notice pages
- the email texts and mail server
- the first solve bonus

It is safe to run again at any time. It never overwrites pages, emails or logos you have edited in the admin
panel.

Refresh `http://localhost:8080`. You should see the CyberPaw home page with the logo and countdown.

## 9. Email (send-only mail server)

The site sends confirmation and password reset emails through Postfix on this VM. It only sends to JWU
addresses.

```
sudo bash /opt/cyberpaw/repo/config/postfix-setup.sh
```

The script prints a DKIM record at the end. In Cloudflare -> `jwucyberlab.org` -> DNS:

1. **SPF:** edit the existing TXT record on `@` that starts with `v=spf1` so it is:
   ```
   v=spf1 ip4:<public IP> include:_spf.mx.cloudflare.net include:_spf.google.com ~all
   ```
   Find `<public IP>` with `curl -s https://ifconfig.me` on the VM.
2. **DKIM:** create or replace the TXT record named `cyberpaw._domainkey` with the value the script printed.
   The value starts with `v=DKIM1;`.

To test, open the login page, click "Forgot your password?" and enter the JWU email of an account on the
site. An email should arrive within a minute.
The first emails may land in Junk until the DNS records spread (up to an hour). Mark them "Not junk".

## 10. Go public (Cloudflare tunnel)

cloudflared is pinned to a known version and never updates itself:

```
cd /tmp
curl -fLO https://github.com/cloudflare/cloudflared/releases/download/2026.10.0/cloudflared-linux-amd64.deb
sudo apt-get install -y ./cloudflared-linux-amd64.deb
sudo apt-mark hold cloudflared
```

Store the tunnel token (root only), then install and start the service from the repo:

```
sudo install -d -m 700 /etc/cloudflared
sudo nano /etc/cloudflared/token        # paste the tunnel token, save
sudo chmod 600 /etc/cloudflared/token
sudo cp /opt/cyberpaw/repo/config/cloudflared.service /etc/systemd/system/cloudflared.service
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared --no-pager
```

The status should say `active (running)` and the log should show `Registered tunnel connection`. Open
https://jwucyberlab.org in a browser.

## 11. Final checks

Work through this list and fix anything that fails before announcing the site:

- [ ] https://jwucyberlab.org shows the CyberPaw home page and the countdown.
- [ ] Log in as the admin. **Admin Panel** shows the top bar: Users, Submissions, Challenges, Pages, Config.
- [ ] Config -> Start and End Time: set the competition start and end.
- [ ] Config -> Registration Code: set or clear the sign-up code.
- [ ] The competition switch at the top of the admin home (Challenges) says **Running** when you want
  players to submit flags.
- [ ] In a private window, register with a JWU email. You get one email, and the account can do nothing
  until the link in it is clicked (while logged in).
- [ ] Add a test challenge from Admin -> Challenges -> **Add challenge**, solve it as the test player, check
  the scoreboard, then delete the test challenge and test account.

The site is ready.

## Day-to-day

| Task | How |
|---|---|
| Add or hide challenges | Admin -> Challenges. "Add challenge" for new ones; the switch on each row shows or hides it |
| Edit Rules, How to Play, Privacy | Admin -> Pages |
| Edit emails | Admin -> Config -> Email Notifications |
| Pause or resume the competition | Competition switch at the top of Admin -> Challenges |
| First solve bonus | Admin -> Config -> Challenges -> First solve bonus (0 turns it off) |
| Preview with fake data | `cd /opt/cyberpaw/repo && sudo bash scripts/seed-demo.sh`; remove with `--wipe`. Never during a competition |

## Updating the site's code

When the repo on GitHub changes:

```
cd /opt/cyberpaw/repo
sudo git pull
sudo cp config/docker-compose.yml /opt/cyberpaw/
sudo docker compose --project-directory /opt/cyberpaw up -d
sudo docker compose --project-directory /opt/cyberpaw restart web
sudo bash scripts/apply-config.sh
```

Browsers and Cloudflare pick up new styles and scripts automatically.

To upgrade CTFd itself, change the image version in `config/docker-compose.yml` on purpose, test it on a
copy first, and re-check the templates listed in `THIRD_PARTY_NOTICES` against the new version.

## Troubleshooting

| Problem | Check |
|---|---|
| Site down | `sudo docker compose --project-directory /opt/cyberpaw ps` and `... logs --tail 100 web` |
| jwucyberlab.org shows a Cloudflare error | `sudo systemctl status cloudflared`. Is another machine also running the tunnel? |
| No emails arrive | `sudo journalctl --since "-30min" \| grep postfix/smtp`: look for `status=sent`. Check Admin -> Config -> Email shows `host.docker.internal`, port 25 |
| Emails go to Junk | SPF and DKIM records in step 9 |
| "Your confirmation link is invalid" | Links expire after 30 minutes. Use "Resend" on the confirm page |

## What's in this repo

```
config/docker-compose.yml     web app, MariaDB and Redis, pinned versions
config/.env.example           names of the secrets the server needs
config/postfix-setup.sh       send-only mail server with DKIM, JWU recipients only
config/cloudflared.service    Cloudflare tunnel service
theme/cyberpaw/               site theme: templates, CSS, JavaScript
theme/assets/                 logos and favicon
theme/pages/                  starting text for How to Play, Rules and Privacy Notice
theme/index.html, motd.html   home page and the rules pop-up shown once to each player
plugins/cyberpaw/             site plugin: difficulty, First Paw bonus, profiles, emails, admin pages
scripts/apply-config.sh       applies the CyberPaw settings (step 8)
scripts/seed-demo.sh          fake data for previews
```
