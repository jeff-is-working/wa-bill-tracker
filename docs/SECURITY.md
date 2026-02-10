# Security Documentation

> Security model, practices, and considerations

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [Content Security Policy](#content-security-policy)
3. [Input Sanitization](#input-sanitization)
4. [Data Privacy](#data-privacy)
5. [API Security](#api-security)
6. [Deployment Security](#deployment-security)
7. [Security Checklist](#security-checklist)

---

## Security Overview

The WA Bill Tracker implements a defense-in-depth security model appropriate for a public-facing static web application.

### Security Posture

| Aspect | Approach |
|--------|----------|
| **Architecture** | Serverless, static files only |
| **Authentication** | None required (public data) |
| **User Data** | Client-side only (browser storage) |
| **API Access** | Public government API |
| **Hosting** | GitHub Pages (managed security) |

### Threat Model

```mermaid
flowchart TB
    subgraph Threats["Potential Threats"]
        XSS["Cross-Site Scripting"]
        INJECT["Injection Attacks"]
        CSRF["Cross-Site Request Forgery"]
        DATA["Data Tampering"]
    end

    subgraph Mitigations["Mitigations"]
        CSP["Content Security Policy"]
        ESCAPE["HTML Escaping"]
        SAMESITE["SameSite Cookies"]
        VALIDATE["Data Validation"]
    end

    XSS --> CSP
    XSS --> ESCAPE
    INJECT --> ESCAPE
    CSRF --> SAMESITE
    DATA --> VALIDATE
```

---

## Content Security Policy

### CSP Headers

The application implements strict Content Security Policy via meta tag:

```html
<meta http-equiv="Content-Security-Policy" content="
    default-src 'none';
    script-src 'self' 'unsafe-inline';
    style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
    font-src 'self' https://fonts.gstatic.com;
    img-src 'self' data:;
    connect-src 'self' https://raw.githubusercontent.com;
    frame-ancestors 'none';
    form-action 'none';
    base-uri 'self';
">
```

### Directive Breakdown

| Directive | Value | Purpose |
|-----------|-------|---------|
| `default-src` | `'none'` | Block all by default |
| `script-src` | `'self' 'unsafe-inline'` | Local scripts only |
| `style-src` | `'self' 'unsafe-inline' fonts.googleapis.com` | Local + Google Fonts |
| `font-src` | `'self' fonts.gstatic.com` | Local + Google Fonts CDN |
| `img-src` | `'self' data:` | Local images + data URIs |
| `connect-src` | `'self' raw.githubusercontent.com` | API connections |
| `frame-ancestors` | `'none'` | Prevent clickjacking |
| `form-action` | `'none'` | Disable form submissions |
| `base-uri` | `'self'` | Prevent base tag hijacking |

### Additional Security Headers

```html
<meta http-equiv="X-Content-Type-Options" content="nosniff">
<meta http-equiv="X-Frame-Options" content="DENY">
<meta name="referrer" content="strict-origin-when-cross-origin">
```

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevent framing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer info |

### Permissions Policy

```html
<meta http-equiv="Permissions-Policy" content="
    camera=(),
    microphone=(),
    geolocation=(),
    payment=()
">
```

Explicitly disables sensitive browser APIs.

---

## Input Sanitization

### HTML Escaping

All user-controlled content is escaped before insertion into DOM:

```javascript
function escapeHTML(str) {
    if (!str) return '';

    const escapeMap = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    };

    return String(str).replace(/[&<>"']/g, char => escapeMap[char]);
}
```

### Usage Pattern

```javascript
// SAFE: Content is escaped
const card = `
    <div class="bill-card">
        <h3>${escapeHTML(bill.title)}</h3>
        <p>${escapeHTML(bill.description)}</p>
        <span>${escapeHTML(bill.sponsor)}</span>
    </div>
`;

// UNSAFE: Never do this
const unsafe = `<div>${bill.title}</div>`;  // XSS risk!
```

### Protected Fields

All user-visible bill fields are escaped:

| Field | Source | Risk | Mitigation |
|-------|--------|------|------------|
| `title` | API | Low | Escaped |
| `description` | API | Low | Escaped |
| `sponsor` | API | Low | Escaped |
| `historyLine` | API | Low | Escaped |
| User notes | User input | High | Escaped |

### URL Validation

External URLs are validated before rendering:

```javascript
function isValidUrl(url) {
    try {
        const parsed = new URL(url);
        return ['http:', 'https:'].includes(parsed.protocol);
    } catch {
        return false;
    }
}

// Only render link if URL is valid
const link = isValidUrl(bill.legUrl)
    ? `<a href="${escapeHTML(bill.legUrl)}" target="_blank" rel="noopener">`
    : '';
```

---

## Data Privacy

### Client-Side Storage

User data never leaves the browser:

```mermaid
flowchart LR
    USER["User Actions"]
    STATE["APP_STATE"]
    COOKIE["Cookies"]
    LOCAL["localStorage"]

    USER --> STATE
    STATE --> COOKIE
    STATE --> LOCAL

    subgraph Browser["Browser (Local Only)"]
        STATE
        COOKIE
        LOCAL
    end
```

### What's Stored

| Data | Storage | Duration | Sensitivity |
|------|---------|----------|-------------|
| Tracked bills | Cookie + localStorage | 90 days | Low |
| User notes | Cookie + localStorage | 90 days | Medium |
| Filter preferences | Cookie + localStorage | 90 days | Low |
| Bill data cache | localStorage | 1 hour | Public data |

### What's NOT Stored

- No personal information collected
- No analytics or tracking
- No server-side user data
- No third-party cookies

### Cookie Security

```javascript
function setCookie(name, value, days) {
    const expires = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${name}=${encodeURIComponent(JSON.stringify(value))}; ` +
        `expires=${expires}; ` +
        `path=/; ` +
        `SameSite=Lax; ` +
        `Secure`;
}
```

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `SameSite` | `Lax` | CSRF protection |
| `Secure` | Set | HTTPS only |
| `Path` | `/` | Site-wide access |
| `Expires` | 90 days | Session persistence |

---

## API Security

### External API Connections

| Service | URL | Authentication |
|---------|-----|----------------|
| WA Legislature | `wslwebservices.leg.wa.gov` | None (public) |
| GitHub Raw | `raw.githubusercontent.com` | None (public) |
| Google Fonts | `fonts.googleapis.com` | None (public) |

### API Data Validation

Data from external APIs is validated before use:

```python
# In validate_bills_json.py
def validate_bill(bill):
    required_fields = ['id', 'number', 'title', 'status']

    # Check required fields
    for field in required_fields:
        if field not in bill:
            return False

    # Validate status enum
    valid_statuses = {'prefiled', 'introduced', 'committee', ...}
    if bill['status'] not in valid_statuses:
        return False

    return True
```

### No Sensitive API Operations

- Read-only API access
- No authentication tokens
- No write operations
- No user data transmission

---

## Deployment Security

### GitHub Pages Security

GitHub Pages provides:

- Automatic HTTPS
- DDoS protection
- Global CDN
- Managed infrastructure

### HTTPS Configuration

```mermaid
flowchart LR
    USER["User"]
    CF["Cloudflare<br/>(DNS)"]
    GH["GitHub Pages<br/>(HTTPS)"]

    USER -->|HTTPS| CF -->|HTTPS| GH
```

- **Forced HTTPS**: Enabled in repository settings
- **TLS Version**: 1.2 minimum
- **Certificate**: Let's Encrypt (auto-renewed)

### Repository Security

| Setting | Status | Purpose |
|---------|--------|---------|
| Branch protection | Recommended | Prevent force push |
| Signed commits | Optional | Verify authorship |
| Dependency alerts | Enabled | CVE notifications |
| Secret scanning | Enabled | Prevent secret leaks |

---

## Security Checklist

### Development

- [ ] Escape all user-controlled content with `escapeHTML()`
- [ ] Validate URLs before rendering as links
- [ ] Use `rel="noopener"` on external links
- [ ] Don't store sensitive data in code
- [ ] Review CSP before deploying changes

### Code Review

- [ ] Check for `innerHTML` without escaping
- [ ] Verify no hardcoded secrets
- [ ] Confirm external URLs are validated
- [ ] Review new dependencies for vulnerabilities

### Deployment

- [ ] HTTPS enforcement enabled
- [ ] CSP headers present
- [ ] No sensitive data in commits
- [ ] Branch protection configured

### Ongoing

- [ ] Monitor GitHub security alerts
- [ ] Review access logs periodically
- [ ] Update dependencies when CVEs reported
- [ ] Test CSP effectiveness

---

## Incident Response

### Security Issue Reporting

1. **Do not** create public GitHub issue
2. Contact repository maintainer directly
3. Provide details of vulnerability
4. Allow time for patch before disclosure

### Response Process

```mermaid
flowchart LR
    REPORT["Report Received"]
    ASSESS["Assess Severity"]
    FIX["Develop Fix"]
    TEST["Test Fix"]
    DEPLOY["Deploy"]
    DISCLOSE["Disclose"]

    REPORT --> ASSESS --> FIX --> TEST --> DEPLOY --> DISCLOSE
```

---

## Security Limitations

### Known Limitations

| Limitation | Risk | Mitigation |
|------------|------|------------|
| `'unsafe-inline'` in CSP | Medium | Required for inline styles |
| Client-side only | Low | No sensitive operations |
| No authentication | Low | Public data only |
| Cookie storage | Low | SameSite + Secure flags |

### Not In Scope

These security concerns don't apply to this application:

- SQL injection (no database)
- Authentication bypass (no auth)
- Session hijacking (no sessions)
- Server-side vulnerabilities (no server)

---

## Related Documentation

- [Architecture & Data Flow](ARCHITECTURE.md) - Security architecture context
- [Deployment & Operations](DEPLOYMENT.md) - Secure deployment, infrastructure
- [Developer Guide](DEVELOPER_GUIDE.md) - Secure coding practices
- [Frontend](FRONTEND.md) - Client-side security (escapeHTML, CSP)

---

*Last updated: February 2026*
