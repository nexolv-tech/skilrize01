# Deploying SkilRize — step by step

This is the full path from "nothing exists yet" to "the site is live," written
so you can follow it without already knowing server admin. Do the steps in
order — later ones depend on earlier ones.

## What you need before starting

- An Oracle Cloud "Always Free" account (or any VPS — these steps work the
  same on Hetzner, DigitalOcean, etc., just skip the Oracle-specific bits)
- A domain name, bought from any registrar (Namecheap, Porkbun, etc.)
- A transactional email provider account (Postmark, SES, Mailgun, etc.) for
  sending real email
- A Backblaze B2 account (free tier) for off-server backups

None of the above can be done for you — they're account creation and/or
payment, so they're yours to do. Everything after "you have a VM with an IP
address" is scripted for you below.

---

## 1. Create the VM

In the Oracle Cloud console: create a new Compute Instance, choose the
**Ampere (ARM) A1** shape, and pick **Ubuntu** as the image (not Oracle
Linux — Ubuntu's firewall tooling is what `setup-firewall.sh` expects).
Give it a public IP. Save the SSH key Oracle gives you.

## 2. Point your domain at it

In your domain registrar's DNS settings, add two records:

| Type | Name  | Value                  |
|------|-------|------------------------|
| A    | @     | (the VM's public IP)   |
| A    | api   | (the VM's public IP)   |
| A    | www   | (the VM's public IP)   |

This makes `your-domain.com`, `www.your-domain.com`, and
`api.your-domain.com` all point at your server. DNS changes can take up to a
few hours to propagate — you can move on to the next steps while you wait,
but the site won't be reachable by domain (only by IP) until this finishes.

## 3. SSH in and install Docker

```bash
ssh ubuntu@<your-vm-ip>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
sudo apt-get update && sudo apt-get install -y git rclone
```

Log out and back in (`exit`, then SSH in again) so the docker group
membership takes effect.

## 4. Clone the repo

```bash
git clone https://github.com/nexolv-tech/skilrize01.git skilrize
cd skilrize
```

## 5. Open the firewall — both places

```bash
sudo ./deploy/setup-firewall.sh
```

This opens ports 22 (SSH), 80 (HTTP), and 443 (HTTPS) on the VM itself, and
blocks everything else. Read the comment at the top of that script — Oracle
also requires you to open 80 and 443 in the **cloud console's Security
List**, which this script cannot do for you. Skip that and the site stays
unreachable even though everything on the server is correct.

## 6. Fill in your secrets

```bash
cp deploy/production.env.example deploy/production.env
nano deploy/production.env
```

Fill in every blank value. For the three Django secrets, generate each one
separately on the VM:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Run that three times for `SECRET_KEY`, `FILE_SIGNING_KEY`, and
`FIELD_ENCRYPTION_KEY` — three different values, not the same one copied
three times.

This file holds real passwords and keys. It is already excluded from git
(see `.gitignore`) — never remove that exclusion or commit this file.

## 7. First boot

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/production.env up -d --build
```

The first run takes a while: it builds both images, downloads ClamAV's virus
database (several minutes), and Caddy requests HTTPS certificates for your
domains. Watch it with:

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/production.env logs -f
```

Once it settles, visit `https://your-domain.com` in a browser. If it doesn't
load: check that DNS has propagated (`dig your-domain.com` should show your
VM's IP), and check the Oracle console Security List from step 5.

## 8. Make yourself the admin

Sign up on the site with the email you will run SkilRize from, then make
that account the Super Admin:

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/production.env exec api python manage.py set_admin_role you@example.com super_admin
```

Sign in again: you are asked to set up an authenticator app (every admin
role requires one), and the account menu then has **Admin console**. From
there you confirm payments, send payouts and refunds, approve identity
checks, and give other people roles (Users → Details). Other roles:
`finance_admin`, `verification_officer`, `moderator`, `support_agent`,
`dispute_officer`; `none` removes one.

Categories and skills are seeded automatically every time the API starts
(`manage.py seed` is idempotent). To list your own services under a real
account — set real prices in `api/core/management/commands/create_storefront.py`
first; the ones in the file are placeholders:

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/production.env exec api python manage.py create_storefront --email you@example.com
```

The account it creates has no password. Use "Forgot password" on the site
to set one, then finish verification from the dashboard. The services start
as drafts, because a service needs at least one picture to go live: sign in,
open Services → Your services, add a picture (and optionally a short MP4
video) to each, and press Publish.

Uploaded pictures and videos are served from the main domain: Caddy sends
`/files/*` straight to the API (see `deploy/Caddyfile`). If you change the
Caddyfile, keep that block above the catch-all.

## 9. Turn on nightly backups

```bash
crontab -e
```

Paste in the line from `deploy/crontab.example`, fixing the path to match
where you cloned the repo. Test it once by hand first so you're not
discovering a typo three weeks from now when you actually need a backup:

```bash
./deploy/backup.sh
```

## 10. Turn on connected accounts (optional)

Settings → Connected accounts lists Zoom, Google Meet, GitHub, Figma and
Notion. Each shows "Coming soon" until you register a free developer app
with that company and put its two keys in `deploy/production.env`. Every
app asks for a **redirect URL**; it is always your domain followed by
`/integrations/callback/` and the provider's name:

| Provider | Redirect URL |
| --- | --- |
| Zoom | `https://your-domain.com/integrations/callback/zoom` |
| Google Meet | `https://your-domain.com/integrations/callback/google_meet` |
| GitHub | `https://your-domain.com/integrations/callback/github` |
| Figma | `https://your-domain.com/integrations/callback/figma` |
| Notion | `https://your-domain.com/integrations/callback/notion` |

Apps that ask for a homepage, privacy policy or terms link take
`https://your-domain.com`, `/privacy` and `/terms`.

- **GitHub** — github.com → Settings → Developer settings → OAuth Apps →
  New OAuth App. Anyone can connect as soon as it exists. Activity is read
  from public repositories only.
- **Zoom** — marketplace.zoom.us → Develop → Build App → General App,
  user-managed. Add the redirect URL (also to the OAuth allow list) and the
  scopes `meeting:write:meeting` and `user:read:user`. Until Zoom approves
  the app in its Marketplace review, only people in your own Zoom account
  can connect.
- **Google Meet** — console.cloud.google.com → a new project → enable the
  Google Calendar API → OAuth consent screen (External) with the scopes
  `calendar.events` and `userinfo.email` → Credentials → OAuth client ID,
  type Web application, with the redirect URL. Calendar access is a
  "sensitive" scope: until Google verifies the app, only test users you add
  (up to 100) can connect, and they see an "unverified app" warning.
- **Figma** — figma.com/developers/apps → create an app with the redirect
  URL and the scope `file_versions:read`. A private app works for your own
  Figma team; publish it (Figma reviews it) for everyone.
- **Notion** — notion.so/profile/integrations → New integration, type
  Public, with the redirect URL and the legal links above, and read-content
  capability only. Notion may ask you to submit it for review first.

Put each app's client ID and secret in `deploy/production.env`, set its
`*_ENABLED=True` (the block is in `production.env.example`), then run
`./deploy/deploy.sh`. Only providers with both keys and the flag set leave
"Coming soon".

## 11. From now on: updating the live site

Never edit files on this server. The workflow is always:

1. On your laptop: write code, commit, `git push` to `main` — exactly like
   you already do.
2. On the server:
   ```bash
   ./deploy/deploy.sh
   ```

That script pulls the latest `main`, rebuilds, runs migrations, and restarts
everything with zero manual steps — Caddy included, whenever the
`Caddyfile` changed. If a deploy ever breaks something, `git
log` on the server tells you exactly which commit went out — `git reset
--hard <previous-commit>` and re-run `deploy.sh` gets you back.

---

## Notes on what's deliberately not here

- **Payments run by bank transfer to your own account** (custodial escrow,
  D42). Set `PLATFORM_BANK_NAME`, `PLATFORM_BANK_ACCOUNT_TITLE` and
  `PLATFORM_BANK_ACCOUNT_NUMBER` in `production.env` before opening for
  business. Until they are set, checkout tells buyers payments are not
  open yet and every funding endpoint refuses (D46). Refunds and payouts
  are sent by hand: Django admin → Payments lists what is owed.
- **Oracle's "Always Free" tier is not a contract.** It's genuinely free, but
  Oracle has a track record of reclaiming accounts it flags as suspicious,
  and free-tier capacity availability varies by region. The nightly backups
  in step 9 are what make that an inconvenience instead of a disaster —
  don't skip them.

## Troubleshooting a small ARM server

- **ClamAV won't start on ARM.** The official `clamav/clamav` image has no
  arm64 build; the stack uses `clamav/clamav-debian`, which does.
- **`npm ci` fails with `EAI_AGAIN` during the build.** Docker's build
  containers can't resolve DNS on some Ubuntu images. Give the daemon
  explicit resolvers in `/etc/docker/daemon.json` —
  `{"dns": ["1.1.1.1", "8.8.8.8"]}` — then `sudo systemctl restart docker`.
- **Builds are slow or get killed on 1 OCPU / 6 GB.** Add a swap file
  (`sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo
  mkswap /swapfile && sudo swapon /swapfile`, plus a line in `/etc/fstab`
  to keep it). The first build takes 15–25 minutes; later ones are faster.
