# Pilot — HTTPS / TLS

Production pilots should terminate TLS at nginx (or a cloud load balancer) and serve the React app + API over HTTPS.

## Automated Let's Encrypt (VM / bare metal)

Script: [`provisioning/scripts/setup-ssl.sh`](../provisioning/scripts/setup-ssl.sh)

**Prerequisites**

- DNS A/AAAA record pointing to the server
- Ports **80** and **443** reachable from the internet
- Docker Compose installed at the repo root

**Run from repository root** (script stops compose briefly to bind port 80):

```bash
cd /path/to/gate-pre.dev_v76
./provisioning/scripts/setup-ssl.sh app.yourdomain.com admin@yourdomain.com
```

The script:

1. Installs `certbot` if needed
2. Obtains certificates via standalone mode
3. Copies certs to `./certs/`
4. Writes `nginx-ssl.conf` for reverse-proxy to API (`:8000`) and frontend (`:3000`)

After certificates exist, point your production compose / nginx stack at `./certs/fullchain.pem` and `./certs/privkey.pem`. Set:

```bash
FRONTEND_URL=https://app.yourdomain.com
CORS_ORIGINS=https://app.yourdomain.com
ENVIRONMENT=production
```

## Renewal

Let's Encrypt certs expire every 90 days. Add a cron job:

```bash
0 3 * * * certbot renew --quiet && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

Adjust paths to match your deployment layout.

## Cloud platforms (Railway, Render, Vercel)

Use the platform's managed TLS on the public URL and set `FRONTEND_URL` / `CORS_ORIGINS` to that HTTPS origin. No local `setup-ssl.sh` required.

## Checklist before go-live

- [ ] `SECRET_KEY` is a random 64-char hex string
- [ ] `ENVIRONMENT=production`
- [ ] SMTP configured (password reset)
- [ ] `SEED_DEMO_USERS=false`
- [ ] Flower / pgweb **not** exposed (`devtools` profile only in dev)
- [ ] HTTPS enforced (redirect HTTP → HTTPS)
