# Contributing to auto_trade_bot

Thank you for your interest in contributing! This project is maintained by **K R HARI PRAJWAL**.

## Ways to Contribute

- 🐛 **Bug reports** — Open a GitHub Issue with steps to reproduce
- 💡 **Feature suggestions** — Open a GitHub Issue with your idea
- 🔧 **Pull requests** — Fork, make changes, open a PR
- 📖 **Documentation** — Improvements to README or docstrings are always welcome
- 🏦 **Broker integrations** — New broker implementations following `BaseBroker` interface
- 📊 **Strategies** — New trading strategies following the `AutoTrader` base class

## Development Setup

```bash
git clone https://github.com/Hariprajwal/auto-trader-bot.git
cd auto-trader-bot

python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
pip install smartapi-python pyotp  # or your broker SDK
```

## Adding a New Broker

1. Create `auto_trade_bot/brokers/yourbroker_broker.py`
2. Inherit from `BaseBroker` and implement all abstract methods
3. Add it to `brokers/__init__.py` factory
4. Add credentials section to `user.cfg.example`
5. Update the README broker table

## Adding a New Strategy

1. Create `auto_trade_bot/strategies/your_strategy.py`
2. Inherit from `AutoTrader`, implement `scout()` and `initialize()`
3. Register it in `strategies/__init__.py` factory
4. Document it in README

## Code Style

- Follow PEP 8
- Add docstrings to all public methods
- Include type hints where possible
- Log important events using the `Logger` instance

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Update README if you add a feature
- Don't commit `user.cfg` or any credentials
- Test with a paper/demo account before submitting

---

*K R HARI PRAJWAL — auto_trade_bot*
