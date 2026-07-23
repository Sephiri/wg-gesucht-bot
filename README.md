# WG-Gesucht Bot 🏠

A dockerized automation tool for WG-Gesucht, built with Python and Playwright. This bot refreshes own listings hourly and sends instant notifications via Telegram.

## Key Features
- **Hourly Refreshes:** Refreshes listings between 75 and 105min during the day and pauses between 00:00 and 08:00 tz=Berlin/Europe:15h
- **Stealth Mode:** Utilizes Playwright with stealth configurations to bypass bot detection.
- **Instant Alerts:** Sends detailed notifications directly to your Telegram chat.
- **Dockerized:** Fully containerized for easy deployment on servers (e.g., Hetzner).

## Tech Stack
- **Python 3.10**
- **Playwright** (Chromium)
- **Docker & Docker Compose**
- **python-dotenv** (Environment Management)

## Getting Started

### 1. Clone the Repository
```bash
git clone git@github.com:Sephiri/wg-gesucht-bot.git
cd wg-gesucht-bot
```

### 2. Configure Environment Variables
```text
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
ASSET_IDS=id1,id2,...  
WG_GESUCHT_EMAIL=your_email
WG_GESUCHT_PASSWORD=your_password
```

### 3. Launch
```bash
docker compose up -d --build
```

### 4. Usage
commands to use in telegram chat
```text
/start : starts the bot in the telegram chat 
/stop : stops the bot (container remains running)
/status : return if bot is running
```