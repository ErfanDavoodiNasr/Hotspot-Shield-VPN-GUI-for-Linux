# Security Policy

## Supported versions

Only the latest `main` branch of this unofficial community project is considered for fixes.

## Reporting a vulnerability

Please open a **private** security advisory on GitHub, or email the repository maintainer.
Do not file public issues that include credentials, tokens, or full client IP addresses.

## Credential policy

- Prefer the desktop keyring.
- Plaintext `credentials.json` is **opt-in only** via `HOTSPOTSHIELD_ALLOW_PLAINTEXT_FALLBACK=1`.
- Secret files under `.secrets/` require `HOTSPOTSHIELD_USE_SECRETS_FILE=1` (and cwd loading also requires
  `HOTSPOTSHIELD_ALLOW_CWD_SECRETS=1`).
- Logs must not contain passwords; redaction is applied in the logging helpers.

## What logs may contain

- Sanitized error messages and CLI technical snippets with secrets redacted.
- Masked IP addresses in documentation/reports (e.g. `203.0.113.xxx`).

## Vendor packages

Vendor `.deb`/`.rpm` files must be downloaded over HTTPS from `repo.hotspotshield.com` and SHA256-verified before
install. Never `curl | sudo bash`.
