#!/bin/bash

# This script sets up the environment and starts freqtrade
# It pulls values from the .env file and passes them as command-line arguments

# Load environment variables
if [ -f .env ]; then
    echo "Loading environment variables from .env file"
    export $(grep -v '^#' .env | xargs)
else
    echo "No .env file found. Please create one with your configuration."
    exit 1
fi

# Start freqtrade with the environment variables
docker-compose down
docker compose build
docker-compose up -d

echo "Freqtrade started with strategy: $STRATEGY"
echo "Web UI available at http://localhost:8081"
echo "Use username 'admin' and password 'admin' to login"