# LAN_MONITORING.md

This document explains how to expose the boss-facing workflow monitor inside the
same office Wi-Fi or LAN as the Mac mini operator box.

The intended use case is:

- `smbagent` runs on a dedicated Mac mini
- the customer owner or boss uses a browser on a Windows PC
- both devices are on the same local network
- the boss gets a read-only progress view
- operator and maintainer controls remain on the Mac mini side

## Recommended topology

- Mac mini:
  - runs the `smbagent` backend
  - stores customer workspaces
  - may expose a read-only monitor page on the local network
- Windows boss machine:
  - does not run `smbagent`
  - opens a browser to the Mac mini's LAN address

## Security model

This document now describes the weaker fallback path.
The preferred commercial path is overlay VPN access; see `VPN_ACCESS.md`.


The LAN monitor is intentionally separate from operator/admin access.

Boss/customer-owner side:

- read-only monitor route:
  - `GET /monitor-login/<customer_id>` for token entry
  - `GET /monitor/<customer_id>` after login cookie is set
- protected by:
  - `monitor_auth.json`
- intended for:
  - viewing workflow status only

Operator/maintainer side:

- SSH access to the Mac mini
- local CLI commands
- maintenance/tuning/recovery
- runtime/admin tokens if separately enabled

Do not share:

- runtime bearer tokens
- admin tokens
- approval ids
- maintenance-only logs or JSON files

## Recommended deployment shape

### 1. Keep the default posture local first

Normal build/validation work should remain local and no-port by default.

Only expose a port after:

- explicit operator approval
- customer need is clear
- network review is complete

### 2. Bind the monitor server to the LAN (fallback only)

On the Mac mini:

```bash
export SMBAGENT_SERVE_HOST=0.0.0.0
export SMBAGENT_SERVE_PORT=8000
```

This allows other machines on the same LAN to reach the server.
Use this only when overlay VPN is not yet available.

### 3. Set the monitor base URL

Use the Mac mini's local network address:

```bash
export SMBAGENT_MONITOR_PUBLIC_BASE_URL=http://192.168.1.50:8000
```

Replace `192.168.1.50` with the real Mac mini LAN IP.

### 4. Issue a read-only monitor token

```bash
smbagent monitor-auth-issue <customer_id> --force
```

This creates a dedicated monitor token in:

- `workspaces/<customer_id>/monitor_auth.json`

### 5. Start the HTTP server

```bash
smbagent serve-http
```

### 6. Give the boss the monitor URL

Example login page:

```text
http://192.168.1.50:8000/monitor-login/acme-dental
```

The boss can open this on a Windows machine in any normal browser, paste the read-only token once, and then continue without the token staying in the URL.

## Windows client expectations

The Windows machine only needs:

- access to the same Wi-Fi or LAN
- a browser such as Edge or Chrome

No software installation is required on the Windows side.

## Firewall and network notes

The Mac mini may need to allow inbound access to the chosen port.

Recommended posture:

- LAN only
- no router port-forwarding
- no public internet exposure

If wider remote access is needed later, prefer:

- VPN
- Tailscale
- zero-trust access layer

not direct public exposure.

## Operational boundary

The boss-facing page is for visibility only.

It should not expose:

- maintenance suggestions
- tuning commands
- maintenance logs
- approval records
- internal failure details beyond simple progress state

Those remain on the operator/maintainer side through:

```bash
smbagent maintenance <customer_id>
smbagent dashboard
smbagent tune show --customer <customer_id>
```

## Delivery checklist

Before handoff, confirm:

- the Mac mini and boss machine are on the same network
- the Mac mini IP is stable enough for the office environment
- `serve-http` is bound to `0.0.0.0` only as an explicit fallback
- the monitor token was issued successfully
- the boss can open the monitor page from Windows
- the page shows only read-only workflow status
- operator/admin tokens were not shared

## Recommended customer explanation

Suggested wording:

> The workflow backend runs on the dedicated Mac mini.  
> From a Windows PC on the same office Wi-Fi, the owner can open a read-only
> browser page to confirm whether the workflow is running, waiting, passed, or
> needs attention.  
> Maintenance, tuning, and operational control remain on the operator side.
