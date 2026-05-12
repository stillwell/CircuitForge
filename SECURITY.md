# CircuitForge — Security Policy

**Version 0.1.0 · 2026**

## Reporting a vulnerability

Please report suspected security issues **privately** to
**andrew.stillwell@enlightec.com** (PGP key on request). Do not open
public GitHub issues for suspected vulnerabilities.

We will acknowledge receipt within **2 business days** and give you a
more detailed update within **10 business days**. We ask that you:

- Give us a reasonable window to patch before public disclosure (90
  days is the default; we will negotiate a shorter window for
  actively-exploited issues).
- Avoid testing against production deployments you do not own; use the
  installer's `--no-gui --venv /tmp/cf-test` option to build a local
  instance.
- Avoid actions that could harm availability or integrity of other
  users' running services.

We are happy to acknowledge researchers in release notes if requested.

## Supported versions

CircuitForge is at an early stage. We patch security issues in the
latest tagged release on the default branch. There is no extended
support window for older minor versions yet.

## Threat model

CircuitForge is a tool for circuit design, simulation, and PCB layout.
Its primary attack surfaces are:

1. **REST API (`run_cloud.py`)** — JWT auth via HMAC-SHA256, PBKDF2-SHA256
   password hashing (200 k iterations, 16-byte salt). Default admin
   password is `admin` and must be changed on first deployment.
2. **Web portal (`run_web.py`)** — session-cookie auth, `HttpOnly` +
   `SameSite=Lax` by default. Set `CIRCUITFORGE_SESSION_SECRET` for
   non-development deployments.
3. **SPICE deck parser** — operates on attacker-controlled text. No
   `eval()` or `exec()` is used; the parser is a regex tokenizer plus
   dispatch. Reports of parser-confusion or denial-of-service via
   crafted decks are welcome.
4. **KiCAD / Eagle / Altium importers** — parse third-party files.
   The KiCAD parser uses an in-house S-expression reader, Eagle uses
   `xml.etree.ElementTree` from the stdlib.
5. **Dependency supply chain** — `numpy`, `scipy`, `flask`,
   `flask-cors`, `gunicorn`, `PyQt5` / `PySide6`, `qrcode`.

## Hardening recommendations

When deploying CircuitForge as a service:

- Always set `CIRCUITFORGE_JWT_SECRET` and
  `CIRCUITFORGE_SESSION_SECRET` to long random values.
- Restrict `CIRCUITFORGE_ALLOWED_ORIGINS` to your trusted origins
  instead of `*`.
- Use the bundled systemd units (`systemd/circuitforge-{api,web}.service`)
  or the Kubernetes manifests (`k8s/deployment.yaml`) — both run as a
  dedicated non-root user with `NoNewPrivileges`, `ProtectSystem=strict`,
  capability drop, and `seccompProfile: RuntimeDefault`.
- Replace the default `admin` user immediately via
  `POST /api/v1/auth/register`.

## Contact

Security disclosures and inquiries:

- **Email**:  andrew.stillwell@enlightec.com
- **Company**: Enlightec Ltd., <https://www.enlightec.com>
- **Maintainer**: Robert Andrew Stillwell
