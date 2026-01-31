# Custom Domain Deployment Plan — wa-bill-tracker.org

> Created: 2026-01-31
> Domain: `wa-bill-tracker.org`
> DNS/SSL Provider: Cloudflare
> Hosting: GitHub Pages

---

## Multiple Custom Domains on the Same GitHub Account

Having another GitHub repo with a different custom domain is **not an issue**. GitHub Pages supports one custom domain per repository independently. Each repo has its own CNAME file and DNS configuration. Your existing custom domain on another repo will be unaffected.

---

## Step-by-Step Deployment Plan

### Step 1: Register Domain (if not already done)

Register `wa-bill-tracker.org` through any registrar. If using Cloudflare Registrar directly, the nameservers are already set. If registered elsewhere, update the nameservers to Cloudflare's assigned pair (found in the Cloudflare dashboard after adding the domain).

---

### Step 2: Add Domain to Cloudflare

1. Log into Cloudflare Dashboard → **Add a Site** → enter `wa-bill-tracker.org`
2. Select the **Free** plan (sufficient for this use case)
3. Cloudflare will scan existing DNS records — clear any that don't apply
4. Note the two Cloudflare nameservers assigned (e.g., `aria.ns.cloudflare.com`, `bob.ns.cloudflare.com`)
5. If domain is registered elsewhere, update nameservers at the registrar to point to Cloudflare

---

### Step 3: Configure Cloudflare DNS Records

In Cloudflare Dashboard → DNS → Records, create the following:

| Type | Name | Content | Proxy | TTL |
|------|------|---------|-------|-----|
| CNAME | `wa-bill-tracker.org` | `jeff-is-working.github.io` | **DNS only** (grey cloud) | Auto |
| CNAME | `www` | `jeff-is-working.github.io` | **DNS only** (grey cloud) | Auto |

**Important:** Set proxy status to **DNS only** (grey cloud icon), not Proxied (orange cloud). GitHub Pages needs to handle TLS directly to issue and renew its Let's Encrypt certificate. Cloudflare proxying will interfere with this.

Alternative approach using A records (if CNAME flattening causes issues):

| Type | Name | Content | Proxy | TTL |
|------|------|---------|-------|-----|
| A | `wa-bill-tracker.org` | `185.199.108.153` | DNS only | Auto |
| A | `wa-bill-tracker.org` | `185.199.109.153` | DNS only | Auto |
| A | `wa-bill-tracker.org` | `185.199.110.153` | DNS only | Auto |
| A | `wa-bill-tracker.org` | `185.199.111.153` | DNS only | Auto |
| CNAME | `www` | `jeff-is-working.github.io` | DNS only | Auto |

These are GitHub's official Pages IP addresses.

---

### Step 4: Configure Cloudflare SSL/TLS Settings

In Cloudflare Dashboard → SSL/TLS:

1. **SSL/TLS encryption mode**: Set to **Full** (not Full Strict, not Flexible)
   - "Full" means Cloudflare connects to GitHub Pages over HTTPS
   - GitHub Pages provides its own Let's Encrypt cert, so Full works correctly
   - If using DNS-only mode (recommended), this setting has no effect — but set it correctly in case you later enable proxying
2. **Edge Certificates** → **Always Use HTTPS**: Enable
3. **Edge Certificates** → **Automatic HTTPS Rewrites**: Enable
4. **Edge Certificates** → **Minimum TLS Version**: TLS 1.2

---

### Step 5: Create CNAME File in Repository

Create a `CNAME` file in the repository root containing the bare domain:

**File: `CNAME`**
```
wa-bill-tracker.org
```

This tells GitHub Pages to serve the site on the custom domain. GitHub will automatically configure the `www` subdomain redirect.

---

### Step 6: Enable Custom Domain in GitHub Pages Settings

1. Go to **GitHub repo → Settings → Pages**
2. Under **Custom domain**, enter: `wa-bill-tracker.org`
3. Click **Save**
4. Wait for DNS check to pass (may take a few minutes)
5. Check **Enforce HTTPS** (GitHub will provision a Let's Encrypt certificate — this can take up to 24 hours but usually completes within minutes)

---

### Step 7: Update Hardcoded URLs in Codebase

Six references need to change from `jeff-is-working.github.io/wa-bill-tracker` to `wa-bill-tracker.org`:

| File | Line | Current | Updated |
|------|------|---------|---------|
| `README.md` | 5 | `https://jeff-is-working.github.io/wa-bill-tracker` | `https://wa-bill-tracker.org` |
| `README.md` | 65 | `https://jeff-is-working.github.io/wa-bill-tracker` | `https://wa-bill-tracker.org` |
| `README.md` | 154 | `https://jeff-is-working.github.io/wa-bill-tracker` | `https://wa-bill-tracker.org` |
| `app.js` | 16 | `siteUrl: 'https://jeff-is-working.github.io/wa-bill-tracker'` | `siteUrl: 'https://wa-bill-tracker.org'` |
| `index.html` | 13 | `og:url` content `https://jeff-is-working.github.io/wa-bill-tracker` | `https://wa-bill-tracker.org` |
| `sbom.json` | 36 | `https://jeff-is-working.github.io/wa-bill-tracker` | `https://wa-bill-tracker.org` |

---

### Step 8: Cloudflare Page Rules (Optional)

If you later switch to **Proxied** mode (orange cloud), add a page rule to redirect `www` to apex:

- **URL**: `www.wa-bill-tracker.org/*`
- **Setting**: Forwarding URL (301 Redirect)
- **Destination**: `https://wa-bill-tracker.org/$1`

This is not needed in DNS-only mode since GitHub Pages handles the redirect.

---

## Execution Order

1. Register domain / add to Cloudflare / configure nameservers
2. Add DNS records in Cloudflare (Step 3)
3. Configure SSL settings in Cloudflare (Step 4)
4. Create `CNAME` file and update hardcoded URLs (Steps 5 + 7)
5. Commit and push changes
6. Configure custom domain in GitHub Pages settings (Step 6)
7. Wait for DNS propagation and HTTPS certificate provisioning
8. Verify site loads at `https://wa-bill-tracker.org`
9. Verify `https://www.wa-bill-tracker.org` redirects to apex domain
10. Verify old URL `https://jeff-is-working.github.io/wa-bill-tracker` redirects to new domain (GitHub handles this automatically)

---

## Verification Checklist

- [ ] `dig wa-bill-tracker.org` returns GitHub Pages IPs or CNAME to `jeff-is-working.github.io`
- [ ] `dig www.wa-bill-tracker.org` returns CNAME to `jeff-is-working.github.io`
- [ ] `https://wa-bill-tracker.org` loads the bill tracker app
- [ ] `https://www.wa-bill-tracker.org` redirects to `https://wa-bill-tracker.org`
- [ ] `https://jeff-is-working.github.io/wa-bill-tracker` redirects to `https://wa-bill-tracker.org`
- [ ] HTTPS certificate is valid (Let's Encrypt, issued by GitHub)
- [ ] No mixed content warnings in browser console
- [ ] Open Graph URL meta tag shows `https://wa-bill-tracker.org`
- [ ] Other GitHub repo's custom domain still works correctly

---

## Notes

- **DNS propagation**: Can take up to 48 hours globally, but typically completes within minutes to a few hours
- **HTTPS certificate**: GitHub Pages uses Let's Encrypt; provisioning requires DNS to resolve correctly first
- **Cloudflare proxy vs DNS-only**: DNS-only (grey cloud) is recommended for GitHub Pages to avoid certificate conflicts. If you want Cloudflare's CDN/WAF features, you can switch to Proxied mode later, but you'll need to use Cloudflare's SSL certificate instead of GitHub's Let's Encrypt cert
- **Old URL redirect**: GitHub automatically 301-redirects the `*.github.io` URL to the custom domain once configured — no action needed
