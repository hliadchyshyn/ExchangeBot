# ExchangeBot

Telegram bot for MonoBank exchange rates. Shows live USD/EUR rates, converts between UAH/USD/EUR, and sends alerts when a rate crosses a threshold.

## Features

| Button | Description |
|--------|-------------|
| 💱 Exchange | Live buy/sell rate for USD or EUR (MonoBank) |
| 📊 Rates | USD/UAH and EUR/UAH at a glance |
| 🔄 Convert | Convert any amount between UAH, USD, EUR |
| 🔔 Alerts | Notify when a rate goes above or below a threshold |
| 📈 History | Official NBU rate for the last 7 days |

## Stack

- Python 3.12
- [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) — Telegram bot
- [aiohttp](https://docs.aiohttp.org) — webhook server
- [Caddy](https://caddyserver.com) — reverse proxy with automatic HTTPS
- [MonoBank API](https://api.monobank.ua) — live exchange rates
- [NBU API](https://bank.gov.ua) — historical rates

## Deploy

### Requirements

- Linux VPS (Ubuntu/Debian)
- Domain pointed at the server (e.g. DuckDNS)
- Python 3.12+
- Caddy

### 1. Clone and configure

```bash
git clone <repo>
cd ExchangeBot
cp .env.example .env
nano .env  # fill in TOKEN and WEBHOOK_HOST
```

### 2. Install Python dependencies

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 3. Set up Caddy

```bash
cp Caddyfile /etc/caddy/Caddyfile
systemctl reload caddy
```

### 4. Run as a systemd service

```bash
cp exchangebot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable exchangebot
systemctl start exchangebot
```

### 5. Check status

```bash
systemctl status exchangebot
journalctl -u exchangebot -f
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TOKEN` | — | Telegram bot token from @BotFather |
| `WEBHOOK_HOST` | `exchangebot.duckdns.org` | Public domain for webhook |
| `PORT` | `8080` | Internal port (Caddy proxies to this) |

## Project structure

```
bot.py                # Bot logic, handlers, webhook server
mono.py               # MonoBank + NBU API client with caching
Caddyfile             # Caddy reverse proxy config
exchangebot.service   # systemd service file
requirements.txt      # Python dependencies
.env.example          # Environment variable template
```
