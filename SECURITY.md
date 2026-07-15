# Security Policy

## Project: auto_trade_bot
**Author: K R HARI PRAJWAL**  
**License: MIT**

---

## Supported Versions

| Version | Supported |
|---|---|
| `main` (latest) | ✅ Yes — actively maintained |
| Older commits | ⚠️ Best-effort only |

---

## Reporting a Vulnerability

If you discover a **security vulnerability** in this project — particularly anything involving:

- Exposure of API keys or broker credentials
- Unsafe handling of `user.cfg` secrets
- Order injection or unintended trade execution
- Dependency vulnerabilities (e.g. in broker SDKs)

**Please do NOT open a public GitHub Issue.**

Instead, report it privately:

1. **Email:** Open a private [GitHub Security Advisory](https://github.com/Hariprajwal/auto-trader-bot/security/advisories/new) on this repository
2. Include a clear description of the vulnerability
3. Include steps to reproduce if possible
4. We will respond within **72 hours**

---

## Security Best Practices for Users

> [!CAUTION]
> Your `user.cfg` contains **live broker API credentials**. Treat it like a password.

### ✅ Do

- Keep `user.cfg` **out of version control** — it is in `.gitignore` by default
- Use **environment variables** (via Docker) instead of `user.cfg` when deploying
- Rotate your broker API key immediately if you suspect it has been exposed
- Use **read + trade only** API permissions — never grant withdrawal permissions
- Run the bot on a **dedicated machine or container** (not your main PC)
- Regularly review `trade_history.json` and your broker's order history for unexpected trades

### ❌ Don't

- Never commit `user.cfg` to a public or private repository
- Never share your `api_key`, `api_secret`, `totp_secret`, or `access_token` with anyone
- Never run this bot with a broker account that has withdrawal permissions enabled via API
- Never expose the bot's host machine ports publicly without authentication

---

## Dependency Security

This project uses the following external dependencies:

| Package | Purpose | Notes |
|---|---|---|
| `sqlalchemy` | Local SQLite database | No network exposure |
| `schedule` | Job scheduling | No network exposure |
| `requests` | Groww broker REST calls | Only calls Groww API endpoints |
| `yfinance` | Backtest data download | Read-only, public market data |
| `smartapi-python` | Angel One broker | Official SDK |
| `kiteconnect` | Zerodha broker | Official SDK |

To check for known vulnerabilities in dependencies:
```bash
pip install pip-audit
pip-audit -r requirements.txt
```

---

## Scope

This security policy covers the **auto_trade_bot** source code only.  
It does **not** cover:
- The broker platforms themselves (Angel One, Zerodha, Groww, etc.)
- NSE/BSE exchange infrastructure
- Your local machine or network security

---

*K R HARI PRAJWAL — auto_trade_bot Security Policy*
