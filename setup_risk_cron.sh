#!/bin/bash

# Setup cron job for automatic risk management
# This script sets up a weekly cron job to run the risk management script

# Get absolute paths
RISK_SCRIPT="$(readlink -f /home/stivi/freqtradeLLM/risk_management.py)"
LOG_FILE="$(readlink -f /home/stivi/freqtradeLLM/risk_management.log)"

# Create a temporary file for the crontab
TEMP_CRON=$(mktemp)

# Export current crontab
crontab -l > "$TEMP_CRON" 2>/dev/null || echo "" > "$TEMP_CRON"

# Check if the job is already in crontab
if ! grep -q "$RISK_SCRIPT" "$TEMP_CRON"; then
    # Add the cron job - runs every Sunday at 1:00 AM
    echo "# FreqTrade Risk Management - Run weekly" >> "$TEMP_CRON"
    echo "0 1 * * 0 $RISK_SCRIPT > $LOG_FILE 2>&1" >> "$TEMP_CRON"
    
    # Install the updated crontab
    crontab "$TEMP_CRON"
    echo "Cron job added successfully. Risk management will run every Sunday at 1:00 AM."
else
    echo "Cron job already exists. No changes made."
fi

# Clean up
rm "$TEMP_CRON"

# Also run the script once now to generate initial pair factors
echo "Running risk management script now to generate initial pair factors..."
python "$RISK_SCRIPT"