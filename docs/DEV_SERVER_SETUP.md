# Dev Server Setup -- Proxmox VM for Internal Testing

## Overview

Minimal hardened Ubuntu Server VM to serve the WA Bill Tracker 2027-session branch on the home LAN. Accessible from any internal device via Pi-hole local DNS and valid HTTPS from Caddy with Cloudflare DNS-challenge certificates.

**Architecture:**

```
Any LAN device
    -> Pi-hole DNS (dev.wa-bill-tracker.org -> VM static IP)
        -> Caddy on VM (HTTPS with real Let's Encrypt cert via Cloudflare DNS challenge)
            -> Static files from /opt/wa-tracker/site
```

**Stack:** Ubuntu 24.04 LTS, Caddy with cloudflare DNS module, Pi-hole local DNS record, cron auto-deploy.

No cloudflared tunnel. No port forwarding. No external exposure. Caddy obtains a valid TLS cert by proving domain ownership through the Cloudflare DNS API (adds a TXT record, gets the cert, removes the TXT record). The cert is real and trusted by all browsers -- no self-signed cert warnings.

---

## Prerequisites

- Proxmox host with available resources (1 vCPU, 1GB RAM, 10GB disk)
- Pi-hole running on the LAN as DNS server
- Cloudflare account managing wa-bill-tracker.org
- Cloudflare API token with Zone:DNS:Edit permission for wa-bill-tracker.org

### Create Cloudflare API Token

1. Go to https://dash.cloudflare.com/profile/api-tokens
2. Create Token > Custom Token
3. Permissions: Zone / DNS / Edit
4. Zone Resources: Include / Specific zone / wa-bill-tracker.org
5. Save the token -- you will need it for Caddy config

---

## 1. Create the Proxmox VM

### VM Specs

| Resource | Value | Notes |
|----------|-------|-------|
| CPU | 1 vCPU | Static site, minimal load |
| RAM | 1 GB | Caddy uses ~50MB |
| Disk | 10 GB | Ubuntu + app + logs |
| Network | Bridge (vmbr0) | Same LAN, static IP |
| OS | Ubuntu 24.04 LTS | Latest LTS |

### Proxmox CLI

```bash
# Download Ubuntu 24.04 cloud image (if not cached)
wget -P /var/lib/vz/template/iso/ \
  https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img

# Create VM (adjust VM ID 200 and storage name as needed)
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

# Cloud-init -- use a STATIC IP so Pi-hole DNS record stays valid
qm set 200 --ciuser jeff
qm set 200 --sshkeys ~/.ssh/authorized_keys
qm set 200 --ipconfig0 ip=192.168.1.50/24,gw=192.168.1.1
# Adjust IP/gateway to match your LAN subnet

qm start 200
```

Note the VM's static IP (e.g., 192.168.1.50) -- you need it for the Pi-hole DNS record.

---

## 2. Base OS Hardening

SSH into the VM and run these steps.

### 2.1 System Updates

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 2.2 Create Service User

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

### 2.4 Firewall

```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 443/tcp   # Caddy HTTPS -- accessible from LAN
sudo ufw allow 80/tcp    # Caddy HTTP -> HTTPS redirect
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

### 2.6 Kernel Hardening

```bash
sudo tee /etc/sysctl.d/99-hardening.conf << 'SYSEOF'
net.ipv4.ip_forward = 0
net.ipv6.conf.all.forwarding = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.log_martians = 1
fs.suid_dumpable = 0
SYSEOF

sudo sysctl --system
```

### 2.7 Cleanup

```bash
sudo apt purge -y snapd telnet rpcbind
sudo apt autoremove -y
sudo timedatectl set-timezone America/Los_Angeles
sudo apt install -y chrony
sudo systemctl enable chrony
```

---

## 3. Install Caddy with Cloudflare DNS Module

Standard Caddy does not include the Cloudflare DNS plugin. Build a custom Caddy binary using xcaddy:

```bash
# Install Go (required for xcaddy)
sudo apt install -y golang

# Install xcaddy
go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest

# Build Caddy with Cloudflare DNS module
~/go/bin/xcaddy build --with github.com/caddy-dns/cloudflare

# Replace system Caddy with the custom build
sudo mv caddy /usr/bin/caddy
sudo chmod +x /usr/bin/caddy

# Install Caddy systemd service (if not already present)
sudo apt install -y caddy
# Then replace the binary again (apt installs the default one)
sudo mv ~/caddy /usr/bin/caddy 2>/dev/null || true
```

Alternative: Download a pre-built Caddy with Cloudflare module from https://caddyserver.com/download (select "cloudflare" under DNS providers).

### Caddyfile

```bash
sudo tee /etc/caddy/Caddyfile << 'CADDYEOF'
dev.wa-bill-tracker.org {
    root * /opt/wa-tracker/site
    file_server

    # TLS via Cloudflare DNS challenge -- no ports exposed to internet
    tls {
        dns cloudflare {env.CLOUDFLARE_API_TOKEN}
    }

    # Security headers (matching GitHub Pages)
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()"
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
    }

    # Cache static assets
    @static path *.css *.js *.json *.png *.ico
    header @static Cache-Control "public, max-age=300"

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
```

### Set the Cloudflare API Token

```bash
sudo mkdir -p /etc/caddy
sudo tee /etc/caddy/environment << 'ENVEOF'
CLOUDFLARE_API_TOKEN=<your-cloudflare-api-token-here>
ENVEOF

sudo chmod 600 /etc/caddy/environment
sudo chown root:root /etc/caddy/environment
```

Update the Caddy systemd service to load the environment file:

```bash
sudo systemctl edit caddy
# Add under [Service]:
# EnvironmentFile=/etc/caddy/environment
```

Or:

```bash
sudo mkdir -p /etc/systemd/system/caddy.service.d
sudo tee /etc/systemd/system/caddy.service.d/override.conf << 'SVCEOF'
[Service]
EnvironmentFile=/etc/caddy/environment
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable caddy
sudo systemctl restart caddy
```

Caddy will now use the Cloudflare API to create a temporary TXT record on `_acme-challenge.dev.wa-bill-tracker.org`, prove ownership to Let's Encrypt, obtain a real trusted cert, and clean up the TXT record. Auto-renews every 60 days.

---

## 4. Configure Pi-hole Local DNS

In the Pi-hole admin panel (or via config file):

1. Go to **Local DNS > DNS Records**
2. Add: `dev.wa-bill-tracker.org` -> `192.168.1.50` (the VM's static IP)
3. Save

Or via CLI on the Pi-hole host:

```bash
echo "192.168.1.50 dev.wa-bill-tracker.org" | sudo tee -a /etc/pihole/custom.list
pihole restartdns
```

Every device on your LAN using Pi-hole as DNS will now resolve `dev.wa-bill-tracker.org` to the VM. Combined with Caddy's real Let's Encrypt cert, browsers get valid HTTPS with no warnings.

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

### 5.3 Cron Auto-Pull

```bash
sudo -u wa-tracker crontab -e
# Add:
*/5 * * * * /opt/wa-tracker/deploy.sh
```

Pulls latest from 2027-session every 5 minutes. Push to the branch from your workstation and the dev server picks it up automatically.

---

## 6. Verification

From any device on the LAN:

```bash
# DNS resolves to the VM
dig dev.wa-bill-tracker.org
# Should return 192.168.1.50

# HTTPS works with valid cert
curl -I https://dev.wa-bill-tracker.org
# Should return 200 with security headers, no cert errors

# Site content loads
curl -s https://dev.wa-bill-tracker.org | head -5
```

Open https://dev.wa-bill-tracker.org in any browser on the network -- should show the C6S-branded 2027-session version with valid HTTPS lock icon.

---

## 7. Maintenance

```bash
# Check services
sudo systemctl status caddy

# Caddy logs
sudo journalctl -u caddy --since "1 hour ago"
cat /var/log/caddy/wa-tracker.log | tail -20

# Deploy log
cat /var/log/wa-tracker-deploy.log | tail -10

# OS updates (auto via unattended-upgrades, manual check)
sudo apt update && sudo apt upgrade -y

# Switch to a different branch
sudo -u wa-tracker bash -c 'cd /opt/wa-tracker/site && git fetch --all && git checkout <branch>'
```

---

## Resource Summary

| Component | Purpose | Port |
|-----------|---------|------|
| Caddy | Static file server + HTTPS (Cloudflare DNS-challenge cert) | 80, 443 (LAN only) |
| Pi-hole | Local DNS: dev.wa-bill-tracker.org -> VM IP | N/A (existing) |
| cron | Auto-deploy from branch every 5 min | N/A |
| SSH | Admin access | 22 |

No internet-facing ports. No tunnel. No port forwarding. Cert issuance happens via Cloudflare API (outbound HTTPS from VM to Cloudflare + Let's Encrypt). All traffic stays on the LAN.

Total footprint: ~50MB RAM idle, <1% CPU.

---

Refs #70
