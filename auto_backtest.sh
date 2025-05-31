#!/bin/bash

# Auto Backtest Script
# This script automatically downloads missing data before running backtests

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
CONFIG_FILE="user_data/config/backtest_config.json"
STRATEGY=""
TIMERANGE=""
TIMEFRAMES="5m,15m,1h,4h"  # Default timeframes to download
EXCHANGE="binance"
DATA_DIR="user_data/data"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --config FILE        Config file path (default: $CONFIG_FILE)"
    echo "  --strategy STRATEGY  Strategy name to backtest"
    echo "  --timerange RANGE    Timerange for backtest (e.g., 20250501-20250530)"
    echo "  --timeframes TF      Comma-separated timeframes to download (default: $TIMEFRAMES)"
    echo "  --exchange EXCHANGE  Exchange name (default: $EXCHANGE)"
    echo "  --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --strategy AdaptiveMomentumStrategy --timerange 20250501-20250530"
    echo "  $0 --strategy EliteQuantStrategy --timerange 20250401-20250430 --timeframes 5m,1h"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --strategy)
            STRATEGY="$2"
            shift 2
            ;;
        --timerange)
            TIMERANGE="$2"
            shift 2
            ;;
        --timeframes)
            TIMEFRAMES="$2"
            shift 2
            ;;
        --exchange)
            EXCHANGE="$2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$STRATEGY" ]]; then
    print_error "Strategy is required. Use --strategy STRATEGY_NAME"
    show_usage
    exit 1
fi

if [[ -z "$TIMERANGE" ]]; then
    print_error "Timerange is required. Use --timerange YYYYMMDD-YYYYMMDD"
    show_usage
    exit 1
fi

# Check if config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    print_error "Config file not found: $CONFIG_FILE"
    exit 1
fi

print_status "Starting auto-backtest process..."
print_status "Strategy: $STRATEGY"
print_status "Timerange: $TIMERANGE"
print_status "Config: $CONFIG_FILE"
print_status "Timeframes: $TIMEFRAMES"

# Extract pairs from config file
print_status "Extracting pair list from config..."
PAIRS=$(python3 -c "
import json
import sys

try:
    with open('$CONFIG_FILE', 'r') as f:
        # Remove comments for proper JSON parsing
        content = f.read()
        lines = content.split('\n')
        clean_lines = [line for line in lines if not line.strip().startswith('//')]
        clean_content = '\n'.join(clean_lines)
        
        config = json.loads(clean_content)
        pairs = config['exchange']['pair_whitelist']
        print(' '.join(pairs))
except Exception as e:
    print(f'Error reading config: {e}', file=sys.stderr)
    sys.exit(1)
")

if [[ $? -ne 0 ]]; then
    print_error "Failed to extract pairs from config file"
    exit 1
fi

print_success "Found $(echo $PAIRS | wc -w) pairs: $PAIRS"

# Download data for each timeframe
IFS=',' read -ra TF_ARRAY <<< "$TIMEFRAMES"
for timeframe in "${TF_ARRAY[@]}"; do
    timeframe=$(echo "$timeframe" | xargs)  # Trim whitespace
    
    print_status "Downloading data for timeframe: $timeframe"
    
    # Build the download command
    download_cmd="docker compose run --rm freqtrade download-data"
    download_cmd="$download_cmd --exchange $EXCHANGE"
    download_cmd="$download_cmd --timeframe $timeframe"
    download_cmd="$download_cmd --timerange $TIMERANGE"
    download_cmd="$download_cmd --pairs $PAIRS"
    download_cmd="$download_cmd --config $CONFIG_FILE"
    
    print_status "Running: $download_cmd"
    
    # Execute the download command
    if eval $download_cmd; then
        print_success "Successfully downloaded data for $timeframe"
    else
        print_warning "Some data might be missing for $timeframe, but continuing..."
    fi
done

# Check data availability
print_status "Checking data availability..."
check_cmd="docker compose run --rm freqtrade list-data --config $CONFIG_FILE"
print_status "Running: $check_cmd"
eval $check_cmd

# Run the backtest
print_status "Starting backtest..."
backtest_cmd="docker compose run --rm freqtrade backtesting"
backtest_cmd="$backtest_cmd --config $CONFIG_FILE"
backtest_cmd="$backtest_cmd --strategy $STRATEGY"
backtest_cmd="$backtest_cmd --timerange $TIMERANGE"

print_status "Running: $backtest_cmd"

if eval $backtest_cmd; then
    print_success "Backtest completed successfully!"
else
    print_error "Backtest failed!"
    exit 1
fi

print_success "Auto-backtest process completed!"
