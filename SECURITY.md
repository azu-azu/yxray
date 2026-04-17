# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest release | Full support — security fixes and features |
| Prior releases | Critical CVE fixes only (for 90 days after supersession) |

## Reporting a Vulnerability

**Please do not report security vulnerabilities via public GitHub issues.**

Use GitHub's private Security Advisory mechanism:

[Report a vulnerability](https://github.com/Laxmi884/alteryx-git-companion/security/advisories/new)

### What to include

A useful report contains:

1. **Affected version** — the release tag or commit SHA you tested against.
2. **Description** — a clear, concise description of the vulnerability.
3. **Steps to reproduce** — step-by-step instructions to trigger the issue.
4. **Impact assessment** — what an attacker could achieve (e.g., RCE, data disclosure, denial of service).
5. **Suggested fix** (optional) — if you have a patch or mitigation idea.

### Response timeline

| Stage | Target |
|-------|--------|
| Initial acknowledgement | Within 72 hours |
| Triage and severity assessment | Within 7 days |
| Fix or mitigation published | Depends on severity (critical: ASAP, high: within 30 days) |
| Public disclosure | Coordinated with reporter after fix is available |

## Scope

Reports are in scope for:

- The Python backend (`src/`, `app/`)
- The React frontend (`app/frontend/`)
- The GitHub Actions CI/CD workflows (`.github/workflows/`)
- The PyInstaller-built `AlteryxGitCompanion.exe` binary

### Out of scope

- Vulnerabilities in third-party dependencies (please report those to the upstream project maintainers)
- Social engineering attacks
- Physical attacks
- Issues in forks or unofficial distributions

## Disclosure Policy

We follow coordinated disclosure. We ask that you give us a reasonable amount of time
to remediate a confirmed vulnerability before publishing details publicly.

We will credit reporters in the release notes unless you prefer anonymity.
