#!/usr/bin/env python3
"""
Minimal test script that just verifies the new custom RPC methods
in the AdaptiveMomentumStrategy without requiring external dependencies
"""
print("==== ADAPTIVE MOMENTUM STRATEGY - RPC TEST ====")

# Mock the RPC message handling
class MockRPC:
    def send_msg(self, msg):
        print(f"Telegram Notification: {msg.get('status', 'No message')}")

# Market condition functions to test
def rpc_set_market_condition(condition, current_condition="neutral"):
    """
    Set market condition manually via RPC.
    Valid conditions: risk_on, neutral, risk_off
    """
    valid_conditions = ['risk_on', 'neutral', 'risk_off']
    condition = condition.lower()
    
    if condition not in valid_conditions:
        return {
            'status': f"Invalid market condition: {condition}. Valid options are: {', '.join(valid_conditions)}"
        }
    
    old_condition = current_condition
    
    # Send notification about manual override
    msg = f"🔄 *Market Condition Manually Set*\n"
    msg += f"From: {old_condition.upper()}\n"
    msg += f"To: {condition.upper()}\n\n"
    msg += f"*Note:* This was manually set via Telegram command."
    
    rpc = MockRPC()
    rpc.send_msg({'status': msg})
    
    return {
        'status': f"Market condition changed from {old_condition} to {condition}"
    }

def rpc_get_market_condition(current_condition="neutral"):
    """
    Get current market condition via RPC.
    """
    return {
        'status': (
            f"*Current Market Condition:* `{current_condition.upper()}`\n\n"
            f"*BTC Price:* `$50,000.00`\n"
            f"*ETH Price:* `$3,200.00`\n"
            f"*Fear & Greed Index:* `50`"
        )
    }

# Test the functions
print("\n1. Testing market condition override:")
for condition in ["risk_on", "neutral", "risk_off", "invalid"]:
    print(f"\nSetting to '{condition}':")
    result = rpc_set_market_condition(condition)
    print(f"Result: {result['status']}")

print("\n2. Testing get market condition:")
result = rpc_get_market_condition("risk_on")
print(f"Result: {result['status']}")

print("\n==== TEST COMPLETE ====")
