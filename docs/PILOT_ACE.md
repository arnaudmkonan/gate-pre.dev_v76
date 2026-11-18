# Pilot — ACE transmission modes

ACE filing uses **`ACETransmitter`** with two modes:

| Mode | When | Behavior |
|------|------|----------|
| **live** | `ACE_SFTP_ENABLED=true` and host/user/key configured | Uploads ABI to CBP SFTP |
| **simulation** | SFTP not configured | Generates `SIM-…` confirmation; entry moves to filing state **without** CBP |

## Production safety

In **`ENVIRONMENT=production`**:

- If SFTP is **not** configured and **`ACE_ALLOW_SIMULATION=false`** (recommended for paid pilots), transmit endpoints **fail** with a clear error instead of simulating.
- If you need demo filing in staging, set `ACE_ALLOW_SIMULATION=true` and monitor responses — every success payload includes `"mode": "simulation"`.

## Environment variables

```bash
ACE_SFTP_ENABLED=false
ACE_ALLOW_SIMULATION=true   # dev/staging only; set false for real production
ACE_SFTP_HOST=
ACE_SFTP_PORT=22
ACE_SFTP_USER=
ACE_SFTP_KEY_PATH=./certs/ace_private_key.pem
ACE_KNOWN_HOSTS_PATH=./certs/ace_known_hosts
```

Check status: `GET /api/ace/transmit/connection` (authenticated).

## Usage metering

Successful transmits (live or simulation) increment **`ace_transmit`** on the entry’s `client_id`. See `GET /api/billing/clients/{client_id}/usage`.
