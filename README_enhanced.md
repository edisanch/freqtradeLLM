# FreqTrade Market Condition Enhancement

This repository contains enhancements to the FreqTrade trading bot, specifically focusing on improving market condition detection and adaptive trading based on changing market conditions.

## Key Features

1. **Enhanced Market Condition Detection**
   - Uses BTC/USDT 4h timeframe as the primary indicator
   - Uses ETH/USDT 4h timeframe as a secondary confirmation indicator
   - Incorporates the Fear and Greed Index as a sentiment indicator
   - For details, see [CHANGELOG_market_condition.md](/user_data/strategies/CHANGELOG_market_condition.md)

2. **Optimized Memory Management**
   - Docker container configured with appropriate memory limits
   - Prevents OOM (Out of Memory) crashes during extended operation

3. **Improved Risk Management**
   - Dynamic position sizing based on market conditions
   - Pair-specific risk factor adjustments

## Usage

### Starting and Restarting FreqTrade

We now have a unified script to manage FreqTrade operations:

```bash
# Basic start/restart
./freqtrade-manager.sh

# Start/restart with container rebuild
./freqtrade-manager.sh --build
```

See [freqtrade-manager-README.md](/freqtrade-manager-README.md) for more details.

### Telegram Commands

The AdaptiveMomentumStrategy now supports custom Telegram commands for monitoring and controlling market condition detection:

- `/getmarketcondition`: Shows the current market condition along with BTC/ETH prices and Fear & Greed index
- `/setmarketcondition <condition>`: Manually override the market condition (options: risk_on, neutral, risk_off)
- `/refreshmarketcondition`: Force a refresh of the market condition analysis

## Strategy Documentation

For detailed information about the AdaptiveMomentumStrategy, please refer to:
- [README.md](/user_data/strategies/README.md) - General strategy information
- [CHANGELOG_market_condition.md](/user_data/strategies/CHANGELOG_market_condition.md) - Details about recent enhancements

## System Requirements

- Docker and Docker Compose
- At least 2GB of available RAM for stable operation
- Internet connection for accessing market data and APIs
