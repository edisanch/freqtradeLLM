#!/bin/bash
# FreqTrade Bot Startup Script for Ecuador Family Trading
echo "🇪🇨 Starting FreqTrade Bot for Ecuador Family Wealth Building..."

# Check if already running
if docker ps | grep -q freqtrade; then
    echo "⚠️  FreqTrade container already running. Stopping first..."
    docker-compose down
    sleep 5
fi

# Start the bot
echo "🚀 Starting FreqTrade in dry-run mode..."
docker-compose up -d

# Wait and check status
sleep 10
if docker ps | grep -q freqtrade; then
    echo "✅ FreqTrade bot started successfully!"
    echo "📊 Access WebUI at: http://localhost:8081"
    echo "👤 Username: admin"
    echo "🔑 Password: admin"
    echo ""
    echo "📱 Check Telegram for bot notifications"
    echo "📈 Monitor trades and adjust strategy as needed"
    
    # Show recent logs
    echo ""
    echo "🔍 Recent logs:"
    docker-compose logs --tail=20 freqtrade
else
    echo "❌ Failed to start FreqTrade bot"
    echo "🔍 Check logs:"
    docker-compose logs freqtrade
fi

echo ""
echo "💪 Remember: Small consistent profits lead to family wealth!"
echo "🎯 Target: 2-5% monthly returns = life-changing money over time"
