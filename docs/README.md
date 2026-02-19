---
title: Documentation Index
scope: Navigation hub for all WA Bill Tracker technical documentation
last_updated: 2026-02-19
---

# Documentation

Welcome to the WA Bill Tracker technical documentation. This index links to all project docs and explains the documentation methodology.

## Documents

| Document | Contents |
|----------|----------|
| [Architecture & Data Flow](ARCHITECTURE.md) | System design, data pipeline, SOAP API integration, data schemas |
| [Frontend](FRONTEND.md) | App state, UI components, filtering, routing, rendering pipeline |
| [Deployment & Operations](DEPLOYMENT.md) | GitHub Pages, CI/CD, custom domain, runbooks, troubleshooting |
| [Developer Guide](DEVELOPER_GUIDE.md) | Setup, coding standards, testing, contributing |
| [Security](SECURITY.md) | Threat model, input sanitization, CSP, data privacy |

The project [README](../README.md) serves as the single source for getting started, installation, and deploying your own instance.

## Quick Links

- **Live site**: [wa-bill-tracker.org](https://wa-bill-tracker.org)
- **Repository**: [github.com/jeff-is-working/wa-bill-tracker](https://github.com/jeff-is-working/wa-bill-tracker)
- **WA Legislature API**: [wslwebservices.leg.wa.gov](https://wslwebservices.leg.wa.gov)

## Documentation Methodology

These docs follow the **Enterprise Documentation v1.2** methodology, which addresses five common documentation problems:

1. **Scattered READMEs** — consolidated into a standard set of purpose-specific documents
2. **Over-fragmented docs** — each section contains substantive content; thin sections are merged
3. **Scattered deployment steps** — setup and deployment live only in README § Getting Started; other docs link there
4. **Context-less code snippets** — every code block has a preceding sentence explaining what it is and why it matters
5. **Poor narrative flow** — documents follow a consistent structure with YAML metadata, limited top-level headings, and cross-references instead of duplication

## Contributing to Docs

When updating documentation:

- Keep each piece of information in exactly one place — cross-reference, never duplicate
- Add a YAML metadata block (`title`, `scope`, `last_updated`) to every new doc
- Limit files to 10 or fewer top-level (`##`) headings
- Provide context before every code snippet or URL
- Update `last_updated` in the metadata block when making changes
