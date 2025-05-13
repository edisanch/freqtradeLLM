# FreqTrade Manager Script

This script provides a unified way to start, restart, and manage your FreqTrade bot instance.

## Features

- **Combined functionality** of both `start-freqtrade.sh` and `restart_freqtrade.sh`
- **Environment variable support** via `.env` file
- **Memory limits** for stable operation
- **Better logging** to both console and log file
- **Container status monitoring** after startup
- **Optional rebuild** with a simple flag

## Usage

```bash
# Basic start/restart
./freqtrade-manager.sh

# Start/restart with container rebuild
./freqtrade-manager.sh --build
# or
./freqtrade-manager.sh -b
```

## .env File Configuration

The script will automatically load variables from a `.env` file in the same directory. Example:

```
STRATEGY=AdaptiveMomentumStrategy
DRY_RUN=true
TELEGRAM_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Logs

Logs are saved to `/home/stivi/freqtradeLLM/freqtrade-manager.log` and include:
- Startup/restart timestamps
- Container status
- Memory usage information
- Environment configuration details

## Web UI Access

After starting, the Web UI will be available at:
- URL: http://localhost:8081
- Default username: admin
- Default password: admin
