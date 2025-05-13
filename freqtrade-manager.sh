#!/bin/bash

# freqtrade-manager.sh - A unified script for starting and restarting FreqTrade
# Combines functionality from both start-freqtrade.sh and restart_freqtrade.sh

# Log file
LOG_FILE="/home/stivi/freqtradeLLM/freqtrade-manager.log"

# Function to log messages both to console and log file
log_message() {
    local message="$(date) - $1"
    echo "$message"
    echo "$message" >> $LOG_FILE
}

# Ensure we're in the right directory
cd /home/stivi/freqtradeLLM

# Load environment variables if .env exists
if [ -f .env ]; then
    log_message "Loading environment variables from .env file"
    export $(grep -v '^#' .env | xargs)
    STRATEGY_INFO="with strategy: $STRATEGY"
else
    log_message "No .env file found. Using default configuration."
    STRATEGY_INFO=""
fi

# Stop any running FreqTrade containers
log_message "Stopping current FreqTrade container"
docker-compose down

# Wait to ensure container is fully stopped
sleep 5

# Build if requested
if [ "$1" == "--build" ] || [ "$1" == "-b" ]; then
    log_message "Building FreqTrade container"
    docker compose build
fi

# Start with memory limits and enable plugins
log_message "Starting FreqTrade with memory limits, enhanced market condition detection, and custom Telegram commands $STRATEGY_INFO"
docker-compose up -d

# Log the status
log_message "FreqTrade container status:"
docker ps --filter "name=freqtrade" --format "{{.Status}}" | tee -a $LOG_FILE

# Log memory usage after start
sleep 10
log_message "Memory usage after start:"
docker stats --no-stream freqtrade | tee -a $LOG_FILE

log_message "FreqTrade operation completed successfully"
log_message "Web UI available at http://localhost:8081"
log_message "Use username 'admin' and password 'admin' to login"
log_message "Custom market condition commands are available in Telegram:"
log_message "  - getmarketcondition"
log_message "  - setmarketcondition risk_on|neutral|risk_off"
log_message "  - refreshmarketcondition"
echo "----------------------------------------" >> $LOG_FILE
