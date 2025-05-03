#!/bin/bash

# FreqTrade Health Check Script
# This script checks if FreqTrade is running properly and sends alerts if not
# Run this as a cron job every 15 minutes: */15 * * * * /home/stivi/freqtradeLLM/health_check.sh

LOG_FILE="/home/stivi/freqtradeLLM/health_check.log"
TELEGRAM_TOKEN=$(grep "token" /home/stivi/freqtradeLLM/config.json | head -1 | cut -d'"' -f4)
TELEGRAM_CHAT_ID=$(grep "chat_id" /home/stivi/freqtradeLLM/config.json | head -1 | cut -d'"' -f4)
MAX_LOG_SIZE=10485760  # 10MB in bytes

# Function to send Telegram message
send_telegram_alert() {
    local message="$1"
    curl -s -X POST https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage \
        -d chat_id=${TELEGRAM_CHAT_ID} \
        -d text="🚨 FreqTrade Alert: ${message}" > /dev/null 2>&1
}

# Log rotation function
rotate_logs() {
    if [ -f "$LOG_FILE" ] && [ $(stat -c%s "$LOG_FILE") -gt $MAX_LOG_SIZE ]; then
        timestamp=$(date +"%Y%m%d-%H%M%S")
        mv "$LOG_FILE" "${LOG_FILE}.${timestamp}"
        # Keep only 5 most recent log files
        ls -t "${LOG_FILE}."* | tail -n +6 | xargs rm -f 2>/dev/null
        echo "$(date) - Log rotation performed" > "$LOG_FILE"
    fi
}

# Perform log rotation
rotate_logs

# Start timestamp
echo "$(date) - Health check started" >> "$LOG_FILE"

# Check if FreqTrade container is running
CONTAINER_STATUS=$(docker ps --filter "name=freqtrade" --format "{{.Status}}")

if [ -z "$CONTAINER_STATUS" ]; then
    echo "$(date) - FreqTrade container is not running!" >> "$LOG_FILE"
    send_telegram_alert "Container is not running. Attempting to restart..."
    
    # Attempt to restart FreqTrade
    cd /home/stivi/freqtradeLLM
    bash start-freqtrade.sh >> "$LOG_FILE" 2>&1
    
    # Check if restart was successful
    sleep 10
    NEW_STATUS=$(docker ps --filter "name=freqtrade" --format "{{.Status}}")
    if [ -z "$NEW_STATUS" ]; then
        send_telegram_alert "Failed to restart FreqTrade container. Manual intervention required."
    else
        send_telegram_alert "FreqTrade container successfully restarted."
    fi
else
    echo "$(date) - Container status: $CONTAINER_STATUS" >> "$LOG_FILE"

    # Check if API is responding (if web UI is enabled)
    API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/api/v1/ping)
    if [ "$API_STATUS" != "200" ]; then
        echo "$(date) - API is not responding properly (status code: $API_STATUS)" >> "$LOG_FILE"
        send_telegram_alert "API is not responding properly (status code: $API_STATUS)"
    else
        echo "$(date) - API is responding properly" >> "$LOG_FILE"
    fi
    
    # Check if there have been trades in the last 24 hours (if running in production)
    # Implement this based on your specific requirements
fi

# Check disk space
DISK_USAGE=$(df -h /home/stivi | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "$(date) - Disk space warning: ${DISK_USAGE}% used" >> "$LOG_FILE"
    send_telegram_alert "Disk space warning: ${DISK_USAGE}% used"
fi

# Check memory usage
MEMORY_FREE=$(free -m | grep "Mem:" | awk '{print $4}')
if [ "$MEMORY_FREE" -lt 500 ]; then
    echo "$(date) - Low memory warning: ${MEMORY_FREE}MB free" >> "$LOG_FILE"
    send_telegram_alert "Low memory warning: ${MEMORY_FREE}MB free"
fi

# End timestamp
echo "$(date) - Health check completed" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"

exit 0