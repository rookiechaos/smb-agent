# VPN Access Posture

This repo now treats overlay VPN access as the preferred commercial posture.

## Default

- keep `SMBAGENT_SERVE_HOST=127.0.0.1`
- keep `SMBAGENT_MONITOR_EXPOSURE=local-only`
- do not open a monitor port during the normal Mac mini workflow

## Preferred remote access

For boss monitor access and remote maintainer SSH access:

Primary default:

- localhost/no-port for the base Mac mini run
- Tailscale for boss monitor and maintainer SSH when remote access is needed

Secondary option:

- WireGuard only for customers who can self-manage VPN peers and key lifecycle


- use an overlay VPN
- recommended first choices:
  - `tailscale`
  - `wireguard`
- keep remote maintenance on `ssh-vpn`
- avoid public Internet exposure
- avoid bare LAN exposure as the normal long-term operating mode

## Suggested env

### Tailscale-first

```bash
export SMBAGENT_MONITOR_EXPOSURE=public-approved
export SMBAGENT_REMOTE_ACCESS_CHANNEL=tailscale
export SMBAGENT_MAINTENANCE_ACCESS_CHANNEL=ssh-vpn
export SMBAGENT_MONITOR_PUBLIC_BASE_URL=https://100.x.y.z:8000
export SMBAGENT_SERVE_HOST=100.x.y.z
export SMBAGENT_SERVE_PORT=8000
```

### WireGuard self-managed

```bash
export SMBAGENT_MONITOR_EXPOSURE=public-approved
export SMBAGENT_REMOTE_ACCESS_CHANNEL=wireguard
export SMBAGENT_MAINTENANCE_ACCESS_CHANNEL=ssh-vpn
export SMBAGENT_MONITOR_PUBLIC_BASE_URL=https://10.x.y.z:8000
export SMBAGENT_SERVE_HOST=10.x.y.z
export SMBAGENT_SERVE_PORT=8000
```

## LAN fallback

Bare LAN monitor exposure is now fallback-only.

To use it explicitly:

```bash
export SMBAGENT_MONITOR_EXPOSURE=lan-only
export SMBAGENT_ALLOW_LAN_MONITOR_FALLBACK=true
export SMBAGENT_SERVE_HOST=0.0.0.0
export SMBAGENT_SERVE_PORT=8000
```

Use this only for on-site same-office viewing when the customer understands that
it is weaker than VPN-based access.

## Boss monitor auth

Preferred owner access is now:

- open `/monitor-login/<customer_id>`
- paste the read-only token once
- receive an HttpOnly cookie
- continue to `/monitor/<customer_id>` without keeping the token in the URL
- use the logout action to clear the monitor cookie when the viewing session ends
- for daily owner access, prefer reverse proxy or overlay HTTPS termination so the cookie remains on a secure path

Query-token monitor URLs should stay disabled except for explicit fallback troubleshooting.
