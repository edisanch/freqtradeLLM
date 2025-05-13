#!/usr/bin/env python3
"""
Simple test script for AdaptiveMomentumStrategy market condition detection
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure we can find the strategy
sys.path.append(str(Path.cwd() / "user_data" / "strategies"))

# Import our strategy class directly
from AdaptiveMomentumStrategy import AdaptiveMomentumStrategy

class MockDataProvider:
    def __init__(self):
        self._msg_queue = []
    
    def get_pair_dataframe(self, pair, timeframe):
        print(f"Mock: Getting {pair} data for {timeframe} timeframe")
        # Return empty dataframe with metadata
        return [], {"pair": pair}

class MockRPC:
    def send_msg(self, msg):
        print(f"TELEGRAM MSG: {msg['status']}")

def test_market_condition():
    """Test the market condition functionality in AdaptiveMomentumStrategy"""
    print("\n=== TESTING ADAPTIVE MOMENTUM STRATEGY MARKET CONDITION ===\n")
    
    # Create basic config
    config = {
        "strategy": "AdaptiveMomentumStrategy",
        "stake_currency": "USDT",
        "dry_run": True,
    }
    
    # Initialize strategy manually
    strategy = AdaptiveMomentumStrategy(config)
    
    # Inject our mocks
    strategy.dp = MockDataProvider()
    strategy._rpc = MockRPC()
    
    # Initialize market check time to force a check
    strategy.last_market_check = datetime.now() - timedelta(days=1)
    strategy.fear_greed_value = 50
    
    # Test set market condition
    print("1. Testing manual market condition override:")
    for condition in ["risk_on", "neutral", "risk_off", "invalid"]:
        print(f"\n-> Setting to '{condition}':")
        result = strategy.rpc_set_market_condition(condition)
        print(f"Result: {result['status']}")
    
    # Test get market condition
    print("\n2. Testing get market condition:")
    result = strategy.rpc_get_market_condition()
    print(f"Result: {result['status']}")
    
    print("\n=== MARKET CONDITION TEST COMPLETE ===")

if __name__ == "__main__":
    test_market_condition()
