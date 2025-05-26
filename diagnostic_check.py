#!/usr/bin/env python3
"""
Diagnostic script to check current market conditions and strategy parameters
"""
import sys
import os
sys.path.append('/freqtrade')

from freqtrade.configuration import Configuration
from freqtrade.resolvers import StrategyResolver
from freqtrade.data.dataprovider import DataProvider
from freqtrade.exchange import get_exchange_bad_reason, validate_exchange
import pandas as pd
import talib.abstract as ta
from datetime import datetime

def main():
    try:
        # Load configuration
        config = Configuration.from_files(['config.json'])
        
        # Load strategy
        strategy = StrategyResolver.load_strategy(config)
        
        # Get exchange
        exchange_class = get_exchange_bad_reason(config['exchange']['name'], config)
        exchange = exchange_class[0](config)
        
        # Create data provider
        dp = DataProvider(config, exchange)
        strategy.dp = dp
        
        print("=" * 60)
        print(f"FREQTRADE DIAGNOSTIC CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Check strategy parameters
        print(f"Strategy: {strategy.__class__.__name__}")
        print(f"Buy RSI threshold: {strategy.buy_rsi}")
        print(f"Sell RSI threshold: {strategy.sell_rsi}")
        print(f"ATR multiplier: {strategy.atr_multiplier}")
        print(f"Market condition: {getattr(strategy, 'market_condition', 'Not set')}")
        
        # Get current market condition
        try:
            current_condition = strategy.get_market_condition()
            print(f"Current market condition: {current_condition}")
        except Exception as e:
            print(f"Error getting market condition: {e}")
        
        # Check active pairs
        pairs = config.get('exchange', {}).get('pair_whitelist', [])
        print(f"\nActive pairs ({len(pairs)}): {pairs[:5]}..." if len(pairs) > 5 else f"\nActive pairs: {pairs}")
        
        # Analyze a few pairs for entry conditions
        print("\n" + "=" * 40)
        print("PAIR ANALYSIS (Last 5 candles)")
        print("=" * 40)
        
        for pair in pairs[:3]:  # Check first 3 pairs
            try:
                # Get recent data
                ohlcv = exchange.get_ohlcv(pair, strategy.timeframe, limit=200)
                if not ohlcv:
                    print(f"{pair}: No data available")
                    continue
                    
                # Convert to DataFrame
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Calculate basic indicators
                df['rsi'] = ta.RSI(df, timeperiod=14)
                df['ema_50'] = ta.EMA(df, timeperiod=50)
                
                # Get last values
                last_row = df.iloc[-1]
                rsi = last_row['rsi']
                close = last_row['close']
                ema_50 = last_row['ema_50']
                
                print(f"\n{pair}:")
                print(f"  Price: ${close:.6f}")
                print(f"  RSI: {rsi:.2f}")
                print(f"  EMA50: ${ema_50:.6f}")
                print(f"  Above EMA50: {close > ema_50}")
                print(f"  RSI < {strategy.buy_rsi}: {rsi < strategy.buy_rsi}")
                print(f"  Entry signal: {rsi < strategy.buy_rsi and close > ema_50}")
                
            except Exception as e:
                print(f"{pair}: Error - {e}")
        
        # Check current balance
        try:
            balance = exchange.get_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            print(f"\nCurrent USDT balance: ${usdt_balance:.2f}")
            print(f"Stake amount per trade: ${config.get('stake_amount', 'Not set')}")
            print(f"Max open trades: {config.get('max_open_trades', 'Not set')}")
        except Exception as e:
            print(f"Error getting balance: {e}")
            
        print("\n" + "=" * 60)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error in diagnostic: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
