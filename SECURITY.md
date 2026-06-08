# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.2.x   | ✅ |
| < 2.2   | ❌ |

## Reporting a Vulnerability

This is a portfolio / demonstration project. If you find a security issue,
please report it privately via GitHub
(**Security → Advisories → Report a vulnerability**), or open an issue without
sensitive details and ask for a private channel.

## Scope & Notes

- The project ships a **deterministic, synthetic / estimated dataset** and does
  not process personal data.
- The optional OpenAI integration reads its API key from a local `.env` file
  (never commit secrets — see `.env.example`). Rule-based insights work without
  any key.
- Cached forecast models (`data/models/*.pkl`) are produced locally; do not load
  `.pkl` files from untrusted sources, as Python's `pickle` can execute arbitrary
  code on load.
- Dependencies are scanned in CI with `pip-audit`, and the source with `bandit`.
