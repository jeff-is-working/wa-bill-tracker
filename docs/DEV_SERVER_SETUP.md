# Dev Server Setup -- Proxmox VM for Internal Testing

## Overview

Minimal hardened Ubuntu Server VM to serve the WA Bill Tracker 2027-session branch on the home LAN. Uses Cloudflare Tunnel (cloudflared) for DNS resolution and SSL termination -- no port forwarding, no reverse proxy, no external exposure.

**Architecture:** Cloudflare DNS -> cloudflared tunnel (outbound only from VM) -> Caddy (static files on localhost)

**Stack:** Ubuntu 24.04 LTS, Caddy (static file server on localhost only), cloudflared (DNS + SSL tunnel), cron auto-deploy.

---

## 1. Create the Proxmox VM

### VM Specs (minimal)

| Resource | Value | Notes |
|----------|-------|-------|
| CPU | 1 vCPU | Static site server, minimal load |
| RAM | 1 GB | Caddy + cloudflared use ~100MB total |
| Disk | 10 GB | Ubuntu + app files + logs |
| Network | Bridge (vmbr0) | Same LAN as workstation |
| OS | Ubuntu 24.04 LTS | Latest LTS with 10-year support |

### Proxmox CLI

```bash
# Download Ubuntu 24.04 cloud image (if not already cached)
wget -P /var/lib/vz/template/iso/ \
  https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img

# Create VM (adjust VM ID and storage as needed)
qm create 200 \
  --name wa-tracker-dev \
  --memory 1024 \
  --cores 1 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --boot order=scsi0

# Import cloud image as disk
qm importdisk 200 /var/lib/vz/template/iso/noble-server-cloudimg-amd64.img local-lvm
qm set 200 --scsi0 local-lvm:vm-200-disk-0,size=10G
qm set 200 --ide2 local-lvm:cloudinit
qm set 200 --serial0 socket --vga serial0

# Cloud-init config
qm set 200 --ciuser jeff
qm set 200 --sshkeys ~/.ssh/authorized_keys
qm set 200 --ipconfig0 ip=dhcp
# Or static IP:
# qm set 200 --ipconfig0 ip=192.168.1.50/24,gw=192.168.1.1

qm start 200
```

Alternatively, use the Proxmox web UI: Create VM > Ubuntu 24.04 ISO > 1 vCPU, 1GB RAM, 10GB disk.

---

## 2. Base OS Hardening (Ubuntu 24.04)

SSH into the VM and run these steps.

### 2.1 System Updates

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 2.2 Create Service User (no sudo, no shell)

```bash
sudo useradd -r -s /usr/sbin/nologin -d /opt/wa-tracker wa-tracker
sudo mkdir -p /opt/wa-tracker/site
sudo chown -R wa-tracker:wa-tracker /opt/wa-tracker
```

### 2.3 SSH Hardening

```bash
sudo tee /etc/ssh/sshd_config.d/hardening.conf << 'SSHEOF'
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
X11Forwarding no
AllowTcpForwarding no
SSHEOF

sudo systemctl restart ssh
```

### 2.4 Firewall (UFW)

```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
# No HTTP/HTTPS ports needed -- Caddy listens on localhost only,
# cloudflared connects to it locally via outbound tunnel
sudo ufw enable
```

### 2.5 Fail2ban

```bash
sudo apt install -y fail2ban
sudo tee /etc/fail2ban/jail.local << 'F2BEOF'
[sshd]
enabled = true
port = ssh
maxretry = 3
bantime = 3600
findtime = 600
F2BEOF

sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 2.6 Kernel Hardening (sysctl)

```bash
sudo tee /etc/sysctl.d/99-hardening.conf << 'SYSEOF'
# Disable IP forwarding
net.ipv4.ip_forward = 0
net.ipv6.conf.all.forwarding = 0

# Ignore ICMP redirects
net.ipv4.conf.all.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0

# Ignore source-routed packets
net.ipv4.conf.all.accept_source_route = 0

# Enable SYN flood protection
net.ipv4.tcp_syncookies = 1

# Log martian packets
net.ipv4.conf.all.log_martians = 1

# Disable core dumps
fs.suid_dumpable = 0
SYSEOF

sudo sysctl --system
```

### 2.7 Remove Unnecessary Packages

```bash
sudo apt purge -y snapd telnet rpcbind
sudo apt autoremove -y
```

### 2.8 Set Timezone and NTP

```bash
sudo timedatectl set-timezone America/Los_Angeles
sudo apt install -y chrony
sudo systemctl enable chrony
```

---

## 3. Install Caddy (Static File Server)

Caddy handles static file serving with automatic HTTPS (via Cloudflare DNS challenge for internal certs).

```bash
# Install Caddy with Cloudflare DNS module (for internal HTTPS certs)
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudflare.com/content/pkg/deb/caddy-cf/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-cloudflare-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/caddy-cloudflare-archive-keyring.gpg] https://dl.cloudflare.com/content/pkg/deb/caddy-cf stable main" | sudo tee /etc/apt/sources.list.d/caddy-cloudflare.list

# If the Cloudflare Caddy build is unavailable, use standard Caddy:
sudo apt install -y caddy
```

### Caddyfile

Caddy listens on localhost only -- cloudflared connects to it locally and handles all external DNS/SSL.

```bash
sudo tee /etc/caddy/Caddyfile << 'CADDYEOF'
:8080 {
    root * /opt/wa-tracker/site
    file_server

    # Security headers (matching GitHub Pages behavior)
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()"
    }

    # Cache static assets
    @static path *.css *.js *.json *.png *.ico
    header @static Cache-Control "public, max-age=3600"

    # SPA fallback
    try_files {path} /index.html

    log {
        output file /var/log/caddy/wa-tracker.log {
            roll_size 10mb
            roll_keep 3
        }
    }
}
CADDYEOF

sudo mkdir -p /var/log/caddy
sudo systemctl enable caddy
sudo systemctl restart caddy
```

---

## 4. Install cloudflared (Tunnel)

No port forwarding. Cloudflare Tunnel creates an outbound-only connection from the VM to Cloudflare's edge, which terminates SSL and resolves DNS.

```bash
# Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb

# Authenticate (opens browser on your workstation -- run this interactively)
cloudflared tunnel login

# Create the tunnel
cloudflared tunnel create wa-tracker-dev

# Note the tunnel ID from the output (e.g., a1b2c3d4-...)
# Configure the tunnel
sudo mkdir -p /etc/cloudflared
sudo tee /etc/cloudflared/config.yml << 'CFEOF'
tunnel: <TUNNEL_ID>
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: dev.wa-bill-tracker.org
    service: http://localhost:8080
  - service: http_status:404
CFEOF

# Route DNS -- creates a CNAME in Cloudflare automatically
cloudflared tunnel route dns wa-tracker-dev dev.wa-bill-tracker.org

# Install as system service
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

### Cloudflare Dashboard Settings

In the Cloudflare dashboard for wa-bill-tracker.org:
- The `dev` CNAME record will be created automatically by `cloudflared tunnel route dns`
- Set the record to **Proxied** (orange cloud) for SSL termination
- Under SSL/TLS > Overview, ensure mode is **Full** or **Full (strict)**

---

## 5. Deploy the App

### 5.1 Initial Clone

```bash
sudo -u wa-tracker git clone \
  --branch 2027-session \
  --single-branch \
  https://github.com/wa-bill-tracker/wa-bill-tracker.git \
  /opt/wa-tracker/site
```

### 5.2 Auto-Deploy Script

Create a script that pulls the latest from the branch:

```bash
sudo tee /opt/wa-tracker/deploy.sh << 'DEPLOYEOF'
#!/bin/bash
set -euo pipefail

SITE_DIR="/opt/wa-tracker/site"
BRANCH="2027-session"
LOG="/var/log/wa-tracker-deploy.log"

echo "$(date -Iseconds) -- Deploying $BRANCH" >> "$LOG"

cd "$SITE_DIR"
git fetch origin "$BRANCH" 2>>"$LOG"
git reset --hard "origin/$BRANCH" 2>>"$LOG"

echo "$(date -Iseconds) -- Deploy complete" >> "$LOG"
DEPLOYEOF

sudo chmod +x /opt/wa-tracker/deploy.sh
sudo chown wa-tracker:wa-tracker /opt/wa-tracker/deploy.sh
sudo touch /var/log/wa-tracker-deploy.log
sudo chown wa-tracker:wa-tracker /var/log/wa-tracker-deploy.log
```

### 5.3 Cron-Based Auto-Pull (simple)

Poll every 5 minutes for changes:

```bash
sudo -u wa-tracker crontab -e
# Add:
*/5 * * * * /opt/wa-tracker/deploy.sh
```

### 5.4 Webhook-Based Auto-Deploy (optional, more responsive)

If you want instant deploys on push, install a lightweight webhook listener:

```bash
sudo apt install -y webhook

sudo tee /etc/webhook.conf << 'WHEOF'
[
  {
    "id": "wa-tracker-deploy",
    "execute-command": "/opt/wa-tracker/deploy.sh",
    "command-working-directory": "/opt/wa-tracker",
    "trigger-rule": {
      "match": {
        "type": "value",
        "value": "refs/heads/2027-session",
        "parameter": {
          "source": "payload",
          "name": "ref"
        }
      }
    }
  }
]
WHEOF

# Run webhook on a non-conflicting port
sudo systemctl enable webhook
# Configure in /etc/default/webhook: WEBHOOK_ARGS="-port 9000"
```

Then add a GitHub webhook in repo settings pointing to the Cloudflare tunnel URL: `https://dev.wa-bill-tracker.org/hooks/wa-tracker-deploy`

---

## 6. Verification Checklist

After setup, verify from your workstation:

```bash
# DNS resolves internally
dig dev.wa-bill-tracker.org

# HTTPS works
curl -I https://dev.wa-bill-tracker.org

# Site serves correctly
curl -s https://dev.wa-bill-tracker.org | head -5

# Security headers present
curl -sI https://dev.wa-bill-tracker.org | grep -E "X-Frame|X-Content"

# SSH hardening
ssh -o PasswordAuthentication=yes jeff@<vm-ip>  # Should be rejected

# Firewall rules
sudo ufw status
```

Open https://dev.wa-bill-tracker.org in a browser -- you should see the C6S-branded 2027-session version with sage green color scheme.

---

## 7. Maintenance

### Updates

```bash
# OS updates (automatic via unattended-upgrades, but manual check)
sudo apt update && sudo apt upgrade -y

# Caddy updates
sudo apt update && sudo apt install --only-upgrade caddy

# cloudflared updates
sudo apt update && sudo apt install --only-upgrade cloudflared
```

### Monitoring

```bash
# Check services
sudo systemctl status caddy cloudflared

# Check logs
sudo journalctl -u caddy --since "1 hour ago"
sudo journalctl -u cloudflared --since "1 hour ago"
cat /var/log/wa-tracker-deploy.log | tail -20
```

### Switch Branch

To test a different branch:

```bash
sudo -u wa-tracker bash -c 'cd /opt/wa-tracker/site && git fetch --all && git checkout <branch>'
```

---

## Resource Summary

| Component | Purpose | Port |
|-----------|---------|------|
| Caddy | Static file server (localhost only) | 8080 (localhost) |
| cloudflared | Outbound tunnel to Cloudflare (DNS + SSL termination) | outbound only |
| cron/webhook | Auto-deploy on branch updates | 9000 (webhook, optional) |
| SSH | Admin access | 22 |

No inbound ports exposed to the network except SSH. cloudflared makes an outbound-only
connection to Cloudflare's edge. Caddy binds to localhost:8080 -- only cloudflared talks to it.

Total resource footprint: ~100MB RAM idle, <1% CPU.

---

Refs #70
