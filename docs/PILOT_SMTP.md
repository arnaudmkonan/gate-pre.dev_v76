# Pilot — Email & Password Reset

GATE sends password reset and notification mail through standard SMTP (SendGrid, Resend SMTP relay, Amazon SES, etc.).

## Required environment variables

| Variable | Example | Notes |
|----------|---------|--------|
| `SMTP_HOST` | `smtp.resend.com` | Provider hostname |
| `SMTP_PORT` | `587` | Usually 587 (TLS) |
| `SMTP_USERNAME` | `resend` | Provider-specific |
| `SMTP_PASSWORD` | *(API key)* | Never commit |
| `SMTP_FROM_EMAIL` | `noreply@yourdomain.com` | Must be authorized by provider |
| `SMTP_TLS` | `true` | Keep enabled for port 587 |
| `FRONTEND_URL` | `https://app.yourdomain.com` | Used in reset links |
| `INSTANCE_URL` | *(optional)* | Overrides `FRONTEND_URL` if set |

Production startup **requires** `SMTP_HOST` when `ENVIRONMENT=production` (see `app/core/config.py`).

## Resend (recommended for pilots)

1. Verify your sending domain in Resend.
2. Create an API key with send permission.
3. Set in `.env`:

```bash
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USERNAME=resend
SMTP_PASSWORD=re_xxxxxxxx
SMTP_FROM_EMAIL=GATE <noreply@yourdomain.com>
FRONTEND_URL=https://app.yourdomain.com
```

## SendGrid

```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=SG.xxxxxxxx
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

## Local development (no SMTP)

If `SMTP_HOST` or `SMTP_USERNAME` is unset, the API **logs** email bodies to the container stdout instead of sending. Password reset still works for QA via `_dev_reset_link` in the JSON response when `ENVIRONMENT=development`.

## Verify the flow

1. Open `http://localhost:3000/forgot-password`
2. Submit a seeded user email (`admin@example.com`)
3. Check API logs for the reset link (dev) or inbox (SMTP configured)
4. Complete reset at `/reset-password?token=...`

API endpoints (unauthenticated): `POST /api/portal/password/forgot`, `POST /api/portal/password/reset`.
