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

## 8. Create your admin account

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/production.env exec api python manage.py createsuperuser
```

## 9. Turn on nightly backups

```bash
chmod +x deploy/backup.sh deploy/deploy.sh
crontab -e
```

Paste in the line from `deploy/crontab.example`, fixing the path to match
where you cloned the repo. Test it once by hand first so you're not
discovering a typo three weeks from now when you actually need a backup:

```bash
./deploy/backup.sh
```

## 10. From now on: updating the live site

Never edit files on this server. The workflow is always:

1. On your laptop: write code, commit, `git push` to `main` — exactly like
   you already do.
2. On the server:
   ```bash
   ./deploy/deploy.sh
   ```

That script pulls the latest `main`, rebuilds, runs migrations, and restarts
everything with zero manual steps. If a deploy ever breaks something, `git
log` on the server tells you exactly which commit went out — `git reset
--hard <previous-commit>` and re-run `deploy.sh` gets you back.

---

## Notes on what's deliberately not here

- **Payments/escrow (Phase 3)** isn't built yet. Everything else — auth,
  email, uploads, 2FA, gigs, projects, campus portals — works live once
  deployed. Don't advertise the site as open for business until payments
  ship; a visitor who tries to pay for something today will hit a wall.
- **Oracle's "Always Free" tier is not a contract.** It's genuinely free, but
  Oracle has a track record of reclaiming accounts it flags as suspicious,
  and free-tier capacity availability varies by region. The nightly backups
  in step 9 are what make that an inconvenience instead of a disaster —
  don't skip them.
