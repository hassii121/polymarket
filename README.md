# Polymarket BTC 5-Minute Automated Trading Bot

A Python-based automated trading bot that monitors Polymarket BTC 5-min Up/Down binary markets and places bets using Martingale staking strategy.

## Project Structure

```
polymarket-bot/
├── config.py           # All settings and API keys
├── signal_engine.py    # TA + sentiment + funding rate analysis
├── martingale.py       # Stake calculator and state management
├── polymarket.py       # Polymarket CLOB API connection
├── bot.py              # Main loop and orchestration
├── dashboard.py        # Terminal display and logging
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
├── Procfile            # Railway deployment config
└── README.md           # This file
```

## Quick Start

1. Clone/setup the project
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your keys
4. Run: `python bot.py`

## System Overview

- **Entry Signal**: Score > 70 (RSI + MACD + EMA + Funding Rate + Fear & Greed + Order Book)
- **Staking**: Martingale $2 → $4 → $8 → $16 → $32 (max 5 levels)
- **Execution**: Polymarket CLOB API with Trust Wallet signing
- **Hosting**: Railway.app with environment variables
