#!/usr/bin/env python3
"""
Enhanced FreqTrade Risk Management Script
This script analyzes trading performance with adaptive 30-day rolling analysis
and provides intelligent risk management insights with trend detection.
Run daily/weekly to reassess strategy performance and make data-driven adjustments
"""
import json
import os
import sqlite3
import argparse
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests


# Configuration
CONFIG_FILE = "/home/stivi/freqtradeLLM/config.json"
DB_FILE = "/home/stivi/freqtradeLLM/tradesv3.dryrun.sqlite"
OUTPUT_DIR = "/home/stivi/freqtradeLLM/user_data/risk_reports"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_telegram_config():
    """Get Telegram config from config.json"""
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    return config.get('telegram', {}).get('token'), config.get('telegram', {}).get('chat_id')

def send_telegram_message(message):
    """Send message via Telegram"""
    token, chat_id = get_telegram_config()
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=data)
        return response.json()
    return None

def get_trades_from_db(days_back=None):
    """Extract trades from SQLite database with optional date filtering"""
    conn = sqlite3.connect(DB_FILE)
    
    if days_back:
        # Calculate date threshold
        cutoff_date = datetime.now() - timedelta(days=days_back)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
        
        query = """
        SELECT pair, close_profit as profit_ratio, open_date, close_date, 
               CAST((julianday(close_date) - julianday(open_date)) * 1440 AS INTEGER) as trade_duration,
               open_rate, close_rate, stake_amount, max_rate, min_rate,
               exit_reason, strategy, enter_tag as tag
        FROM trades
        WHERE close_date IS NOT NULL
        AND close_date >= ?
        ORDER BY close_date DESC
        """
        trades = pd.read_sql_query(query, conn, params=(cutoff_str,))
    else:
        # Get all trades
        query = """
        SELECT pair, close_profit as profit_ratio, open_date, close_date, 
               CAST((julianday(close_date) - julianday(open_date)) * 1440 AS INTEGER) as trade_duration,
               open_rate, close_rate, stake_amount, max_rate, min_rate,
               exit_reason, strategy, enter_tag as tag
        FROM trades
        WHERE close_date IS NOT NULL
        ORDER BY close_date DESC
        """
        trades = pd.read_sql_query(query, conn)
    
    conn.close()
    return trades

def get_trades_between_dates(start_days_back, end_days_back):
    """Get trades between specific date ranges"""
    conn = sqlite3.connect(DB_FILE)
    
    start_date = datetime.now() - timedelta(days=start_days_back)
    end_date = datetime.now() - timedelta(days=end_days_back)
    
    start_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
    end_str = end_date.strftime('%Y-%m-%d %H:%M:%S')
    
    query = """
    SELECT pair, close_profit as profit_ratio, open_date, close_date, 
           CAST((julianday(close_date) - julianday(open_date)) * 1440 AS INTEGER) as trade_duration,
           open_rate, close_rate, stake_amount, max_rate, min_rate,
           exit_reason, strategy, enter_tag as tag
    FROM trades
    WHERE close_date IS NOT NULL
    AND close_date >= ? AND close_date < ?
    ORDER BY close_date DESC
    """
    
    trades = pd.read_sql_query(query, conn, params=(end_str, start_str))
    conn.close()
    return trades

def calculate_metrics(trades):
    """Calculate key performance metrics"""
    if trades.empty:
        return {
            'total_trades': 0,
            'win_count': 0,
            'loss_count': 0,
            'win_rate': 0,
            'profit_sum': 0,
            'average_profit': 0,
            'max_drawdown': 0,
            'profit_factor': 0,
            'sharpe_ratio': 0,
            'expectancy': 0,
            'avg_trade_duration': 0,
            'trades_per_day': 0
        }
    
    metrics = {}
    
    # Basic metrics
    metrics['total_trades'] = len(trades)
    metrics['win_count'] = len(trades[trades['profit_ratio'] > 0])
    metrics['loss_count'] = len(trades[trades['profit_ratio'] <= 0])
    metrics['win_rate'] = metrics['win_count'] / metrics['total_trades'] if metrics['total_trades'] > 0 else 0
    metrics['profit_sum'] = trades['profit_ratio'].sum()
    metrics['average_profit'] = trades['profit_ratio'].mean()
    
    # Risk metrics
    metrics['max_drawdown'] = calculate_max_drawdown(trades)
    metrics['profit_factor'] = calculate_profit_factor(trades)
    metrics['sharpe_ratio'] = calculate_sharpe(trades)
    metrics['expectancy'] = calculate_expectancy(trades)
    
    # Time-based metrics
    metrics['avg_trade_duration'] = trades['trade_duration'].mean()
    metrics['trades_per_day'] = calculate_trades_per_day(trades)
    
    return metrics

def calculate_max_drawdown(trades):
    """Calculate maximum drawdown"""
    if trades.empty:
        return 0
        
    trades_sorted = trades.sort_values('close_date')
    cumulative = (1 + trades_sorted['profit_ratio']).cumprod()
    peak = cumulative.expanding(min_periods=1).max()
    drawdown = (cumulative / peak) - 1
    return drawdown.min()

def calculate_profit_factor(trades):
    """Calculate profit factor (gross profit / gross loss)"""
    if trades.empty:
        return 0
        
    gross_profit = trades.loc[trades['profit_ratio'] > 0, 'profit_ratio'].sum()
    gross_loss = abs(trades.loc[trades['profit_ratio'] < 0, 'profit_ratio'].sum())
    return gross_profit / gross_loss if gross_loss != 0 else float('inf')

def calculate_sharpe(trades, risk_free_rate=0.02/365):
    """Calculate Sharpe ratio"""
    if len(trades) < 2:
        return 0
        
    daily_returns = []
    trades_sorted = trades.sort_values('close_date')
    
    # Group trades by day and calculate daily returns
    trades_sorted['date'] = pd.to_datetime(trades_sorted['close_date']).dt.date
    daily_totals = trades_sorted.groupby('date')['profit_ratio'].sum()
    
    returns_std = daily_totals.std()
    returns_mean = daily_totals.mean()
    
    if returns_std == 0:
        return 0
        
    return (returns_mean - risk_free_rate) / returns_std * np.sqrt(365)

def calculate_expectancy(trades):
    """Calculate system expectancy (average win * win rate - average loss * loss rate)"""
    if trades.empty:
        return 0
        
    wins = trades[trades['profit_ratio'] > 0]
    losses = trades[trades['profit_ratio'] < 0]
    
    win_rate = len(wins) / len(trades) if len(trades) > 0 else 0
    loss_rate = len(losses) / len(trades) if len(trades) > 0 else 0
    
    avg_win = wins['profit_ratio'].mean() if not wins.empty else 0
    avg_loss = losses['profit_ratio'].mean() if not losses.empty else 0
    
    return (avg_win * win_rate) + (avg_loss * loss_rate)

def calculate_trades_per_day(trades):
    """Calculate average trades per day"""
    if trades.empty:
        return 0
        
    trades_sorted = trades.sort_values('close_date')
    start_date = pd.to_datetime(trades_sorted['open_date'].min()).date()
    end_date = pd.to_datetime(trades_sorted['close_date'].max()).date()
    days = (end_date - start_date).days + 1
    return len(trades) / days if days > 0 else 0

def analyze_by_pair(trades):
    """Analyze performance by trading pair"""
    if trades.empty:
        return pd.DataFrame()
        
    # Check if pair column exists
    if 'pair' not in trades.columns:
        print("Warning: 'pair' column not found in trades data")
        print(f"Available columns: {list(trades.columns)}")
        return pd.DataFrame()
        
    try:
        # Group by pair and calculate metrics
        pair_metrics = trades.groupby('pair').agg({
            'profit_ratio': ['count', 'mean', 'sum', 'std'],
            'trade_duration': 'mean'
        })
        
        # Flatten the multi-level column index
        pair_metrics.columns = ['trade_count', 'avg_profit', 'total_profit', 'profit_std', 'avg_duration']
        pair_metrics = pair_metrics.reset_index()
        
        # Calculate win rate per pair
        win_counts = trades[trades['profit_ratio'] > 0].groupby('pair').size()
        pair_metrics['win_count'] = pair_metrics['pair'].map(win_counts).fillna(0).astype(int)
        pair_metrics['win_rate'] = pair_metrics['win_count'] / pair_metrics['trade_count']
        
        # Calculate expectancy per pair
        pair_metrics['expectancy'] = pair_metrics.apply(
            lambda row: calculate_pair_expectancy(trades, row['pair']), 
            axis=1
        )
        
        return pair_metrics.sort_values('expectancy', ascending=False)
        
    except Exception as e:
        print(f"Error in analyze_by_pair: {e}")
        print(f"Trades shape: {trades.shape}")
        print(f"Available columns: {list(trades.columns)}")
        print(f"Sample data:\n{trades.head()}")
        return pd.DataFrame()
def calculate_pair_expectancy(trades, pair):
    """Calculate expectancy for a specific pair"""
    pair_trades = trades[trades['pair'] == pair]
    wins = pair_trades[pair_trades['profit_ratio'] > 0]
    losses = pair_trades[pair_trades['profit_ratio'] < 0]
    
    win_rate = len(wins) / len(pair_trades) if len(pair_trades) > 0 else 0
    loss_rate = len(losses) / len(pair_trades) if len(pair_trades) > 0 else 0
    
    avg_win = wins['profit_ratio'].mean() if not wins.empty else 0
    avg_loss = losses['profit_ratio'].mean() if not losses.empty else 0
    
    return (avg_win * win_rate) + (avg_loss * loss_rate)

def calculate_factor_from_metrics(metrics_row):
    """
    Convert pair metrics to a position sizing factor
    Considers expectancy, win rate, trade volume, and total profit impact
    """
    expectancy = metrics_row['expectancy']
    win_rate = metrics_row['win_rate']
    trade_count = metrics_row['trade_count']
    total_profit = metrics_row['total_profit']
    
    # Base factor from expectancy (primary driver)
    if expectancy > 0:
        base_factor = 1.0 + min(expectancy * 8, 0.5)  # Cap positive adjustment at 0.5
    else:
        base_factor = 1.0 + max(expectancy * 4, -0.5)  # Cap negative adjustment at -0.5
    
    # Adjust for win rate (secondary factor)
    win_rate_adjustment = (win_rate - 0.5) * 0.3  # ±0.15 max adjustment
    
    # Statistical confidence (more trades = more reliable)
    confidence_factor = min(1.0, trade_count / 15)  # Max confidence at 15+ trades
    
    # Total profit impact (considers dollar impact)
    profit_adjustment = 0
    if abs(total_profit) > 0.03:  # Only if significant profit/loss (3%+)
        if total_profit > 0:
            profit_adjustment = min(total_profit * 1.5, 0.3)  # Cap positive at 0.3
        else:
            profit_adjustment = max(total_profit * 2, -0.4)   # Cap negative at -0.4
    
    # Combine factors with weights
    final_factor = (
        base_factor + 
        (win_rate_adjustment * confidence_factor) + 
        (profit_adjustment * confidence_factor)
    )
    
    return final_factor

def analyze_performance_trends(weekly_metrics, monthly_metrics, quarterly_metrics):
    """Analyze if strategy performance is improving, declining, or stable"""
    trends = {}
    
    # Skip if any metrics are None or have no trades
    if not all([weekly_metrics, monthly_metrics, quarterly_metrics]):
        return {
            'win_rate': 'insufficient_data',
            'profit': 'insufficient_data', 
            'overall': 'insufficient_data'
        }
    
    if any(m['total_trades'] == 0 for m in [weekly_metrics, monthly_metrics, quarterly_metrics]):
        return {
            'win_rate': 'insufficient_data',
            'profit': 'insufficient_data',
            'overall': 'insufficient_data'
        }
    
    # Win rate trend
    if weekly_metrics['win_rate'] > monthly_metrics['win_rate'] > quarterly_metrics['win_rate']:
        trends['win_rate'] = 'improving'
    elif weekly_metrics['win_rate'] < monthly_metrics['win_rate'] < quarterly_metrics['win_rate']:
        trends['win_rate'] = 'declining'
    else:
        trends['win_rate'] = 'stable'
    
    # Profit trend (normalized by time period)
    weekly_daily_profit = weekly_metrics['profit_sum'] / 7
    monthly_daily_profit = monthly_metrics['profit_sum'] / 30
    quarterly_daily_profit = quarterly_metrics['profit_sum'] / 90
    
    if weekly_daily_profit > monthly_daily_profit > quarterly_daily_profit:
        trends['profit'] = 'improving'
    elif weekly_daily_profit < monthly_daily_profit < quarterly_daily_profit:
        trends['profit'] = 'declining'
    else:
        trends['profit'] = 'stable'
    
    # Expectancy trend
    if weekly_metrics['expectancy'] > monthly_metrics['expectancy'] > quarterly_metrics['expectancy']:
        trends['expectancy'] = 'improving'
    elif weekly_metrics['expectancy'] < monthly_metrics['expectancy'] < quarterly_metrics['expectancy']:
        trends['expectancy'] = 'declining'
    else:
        trends['expectancy'] = 'stable'
    
    # Overall strategy health
    improving_count = sum(1 for trend in [trends['win_rate'], trends['profit'], trends['expectancy']] if trend == 'improving')
    declining_count = sum(1 for trend in [trends['win_rate'], trends['profit'], trends['expectancy']] if trend == 'declining')
    
    if improving_count >= 2:
        trends['overall'] = 'strong_uptrend'
    elif declining_count >= 2:
        trends['overall'] = 'concerning_downtrend'
    else:
        trends['overall'] = 'mixed_signals'
    
    return trends

def apply_trend_adjustments(factors, trends):
    """Apply macro adjustments based on overall strategy trends"""
    if trends['overall'] == 'insufficient_data':
        return factors
    
    adjustment_factor = 1.0
    
    if trends['overall'] == 'strong_uptrend':
        adjustment_factor = 1.05  # Slightly more aggressive (5% increase)
    elif trends['overall'] == 'concerning_downtrend':
        adjustment_factor = 0.90  # More conservative (10% decrease)
    
    # Apply adjustment to all factors
    adjusted_factors = {pair: factor * adjustment_factor 
                       for pair, factor in factors.items()}
    
    return adjusted_factors

def generate_adaptive_pair_factors(monthly_trades, min_trades_threshold=5):
    """
    Generate pair factors with adaptive logic:
    - Recent 30-day performance gets 70% weight
    - Historical performance gets 30% weight (for stability)
    - Minimum trade threshold to avoid overfitting
    """
    
    print("🔍 Generating adaptive pair factors...")
    
    # Debug: Check monthly trades
    if monthly_trades.empty:
        print("⚠️ No monthly trades data available")
        return {}
    
    print(f"Monthly trades: {len(monthly_trades)} trades")
    print(f"Available columns: {list(monthly_trades.columns)}")
    
    # Get historical trades (31-90 days back for comparison)
    historical_trades = get_trades_between_dates(90, 31)
    print(f"Historical trades: {len(historical_trades)} trades")
    
    # Calculate recent and historical performance
    recent_metrics = analyze_by_pair(monthly_trades)
    historical_metrics = analyze_by_pair(historical_trades)
    
    print(f"Recent metrics: {len(recent_metrics)} pairs")
    print(f"Historical metrics: {len(historical_metrics)} pairs")
    
    # Combine with weighted average
    pair_factors = {}
    
    # Get all unique pairs from monthly trades
    if 'pair' in monthly_trades.columns:
        all_pairs = set(monthly_trades['pair'].unique())
        print(f"Found {len(all_pairs)} unique pairs: {list(all_pairs)[:10]}...")  # Show first 10
    else:
        print("❌ No 'pair' column found in monthly trades")
        return {}
    
    for pair in all_pairs:
        try:
            # Find pair in recent metrics
            recent_data = recent_metrics[recent_metrics['pair'] == pair] if not recent_metrics.empty else pd.DataFrame()
            historical_data = historical_metrics[historical_metrics['pair'] == pair] if not historical_metrics.empty else pd.DataFrame()
            
            has_recent = not recent_data.empty and recent_data.iloc[0]['trade_count'] >= min_trades_threshold
            has_historical = not historical_data.empty and historical_data.iloc[0]['trade_count'] >= min_trades_threshold
            
            if has_recent and has_historical:
                # Both available - use weighted combination
                recent_factor = calculate_factor_from_metrics(recent_data.iloc[0])
                historical_factor = calculate_factor_from_metrics(historical_data.iloc[0])
                
                # 70% recent, 30% historical
                factor = (recent_factor * 0.7) + (historical_factor * 0.3)
                
            elif has_recent:
                # Only recent data available
                factor = calculate_factor_from_metrics(recent_data.iloc[0])
                
            elif has_historical:
                # Only historical data available
                factor = calculate_factor_from_metrics(historical_data.iloc[0])
                
            else:
                # Not enough data - calculate simple factor from raw trades
                pair_trades = monthly_trades[monthly_trades['pair'] == pair]
                if len(pair_trades) >= 3:  # Minimum 3 trades
                    win_rate = (pair_trades['profit_ratio'] > 0).mean()
                    avg_profit = pair_trades['profit_ratio'].mean()
                    
                    # Simple factor calculation
                    factor = 1.0 + (avg_profit * 5) + ((win_rate - 0.5) * 0.5)
                    factor = max(0.5, min(1.5, factor))  # Conservative bounds
                else:
                    factor = 1.0  # Neutral for very limited data
            
            # Apply final bounds (0.3 to 2.0)
            factor = max(0.3, min(2.0, factor))
            pair_factors[pair] = factor
            
        except Exception as e:
            print(f"⚠️ Error processing pair {pair}: {e}")
            pair_factors[pair] = 1.0  # Safe default
    
    print(f"✅ Generated factors for {len(pair_factors)} pairs")
    return pair_factors

def enhanced_risk_management_workflow(mode='adaptive'):
    """
    Enhanced workflow that considers different time horizons
    """
    print(f"🔄 Starting Enhanced Risk Management Analysis (mode: {mode})...")
    
    if mode == 'adaptive':
        # 1. Get different time horizons
        recent_trades = get_trades_from_db(days_back=7)    # Last week
        monthly_trades = get_trades_from_db(days_back=30)  # Last month
        quarterly_trades = get_trades_from_db(days_back=90) # Last quarter
        
        print(f"📊 Data loaded: {len(recent_trades)} weekly, {len(monthly_trades)} monthly, {len(quarterly_trades)} quarterly trades")
        
        # 2. Generate adaptive factors
        adaptive_factors = generate_adaptive_pair_factors(monthly_trades)
        
        # 3. Performance trend analysis
        weekly_metrics = calculate_metrics(recent_trades)
        monthly_metrics = calculate_metrics(monthly_trades)
        quarterly_metrics = calculate_metrics(quarterly_trades)
        
        # 4. Detect performance trends
        trends = analyze_performance_trends(weekly_metrics, monthly_metrics, quarterly_metrics)
        
        # 5. Apply trend-based adjustments
        final_factors = apply_trend_adjustments(adaptive_factors, trends)
        
        # 6. Save enhanced factors
        save_enhanced_factors(final_factors, trends, monthly_metrics)
        
        return final_factors, trends, {
            'weekly': weekly_metrics,
            'monthly': monthly_metrics,
            'quarterly': quarterly_metrics
        }
    
    else:
        # Traditional mode - use all historical data
        all_trades = get_trades_from_db()
        pair_metrics = analyze_by_pair(all_trades)
        
        if pair_metrics.empty:
            factors = {}
        else:
            factors = {}
            for _, row in pair_metrics.iterrows():
                factor = calculate_factor_from_metrics(row)
                factor = max(0.3, min(2.0, factor))  # Apply bounds
                factors[row['pair']] = factor
        
        # Save simple factors
        factors_path = '/home/stivi/freqtradeLLM/user_data/pair_factors.json'
        with open(factors_path, 'w') as f:
            json.dump(factors, f, indent=4)
        
        return factors, {}, {'overall': calculate_metrics(all_trades)}

def save_enhanced_factors(factors, trends, monthly_metrics):
    """Save factors with metadata about trends and timestamp"""
    timestamp = datetime.now().isoformat()
    
    # Enhanced factor file with metadata
    enhanced_data = {
        'timestamp': timestamp,
        'analysis_period_days': 30,
        'trend_analysis': trends,
        'monthly_performance': monthly_metrics,
        'pair_factors': factors,
        'metadata': {
            'total_pairs': len(factors),
            'avg_factor': sum(factors.values()) / len(factors) if factors else 1.0,
            'max_factor': max(factors.values()) if factors else 1.0,
            'min_factor': min(factors.values()) if factors else 1.0,
            'aggressive_pairs': sum(1 for f in factors.values() if f > 1.2),
            'conservative_pairs': sum(1 for f in factors.values() if f < 0.8)
        }
    }
    
    # Save enhanced version
    enhanced_path = '/home/stivi/freqtradeLLM/user_data/enhanced_pair_factors.json'
    with open(enhanced_path, 'w') as f:
        json.dump(enhanced_data, f, indent=4)
    
    # Save simple version for strategy compatibility
    simple_path = '/home/stivi/freqtradeLLM/user_data/pair_factors.json'
    with open(simple_path, 'w') as f:
        json.dump(factors, f, indent=4)
    
    print(f"✅ Enhanced factors saved to {enhanced_path}")
    print(f"✅ Strategy factors saved to {simple_path}")
    
    # Print summary
    print(f"\n📈 Factor Summary:")
    print(f"   Total pairs: {enhanced_data['metadata']['total_pairs']}")
    print(f"   Average factor: {enhanced_data['metadata']['avg_factor']:.3f}")
    print(f"   Aggressive pairs (>1.2): {enhanced_data['metadata']['aggressive_pairs']}")
    print(f"   Conservative pairs (<0.8): {enhanced_data['metadata']['conservative_pairs']}")
    print(f"   Overall trend: {trends.get('overall', 'unknown')}")

def create_enhanced_telegram_report(factors, trends, metrics_comparison, mode):
    """Create enhanced Telegram report with trend analysis"""
    message = f"*🔄 Enhanced Risk Management Report*\n"
    message += f"Mode: {mode} | {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    if mode == 'adaptive' and 'monthly' in metrics_comparison:
        monthly = metrics_comparison['monthly']
        weekly = metrics_comparison['weekly']
        
        message += f"*📊 30-Day Performance*\n"
        message += f"Total Trades: {monthly['total_trades']}\n"
        message += f"Win Rate: {monthly['win_rate']:.1%}\n"
        message += f"Total Profit: {monthly['profit_sum']:.2%}\n"
        message += f"Expectancy: {monthly['expectancy']:.4f}\n"
        message += f"Sharpe Ratio: {monthly['sharpe_ratio']:.2f}\n\n"
        
        # Trend analysis
        if trends.get('overall') != 'insufficient_data':
            message += f"*📈 Trend Analysis*\n"
            message += f"Overall: {trends['overall'].replace('_', ' ').title()}\n"
            message += f"Win Rate: {trends['win_rate'].title()}\n"
            message += f"Profit: {trends['profit'].title()}\n"
            message += f"Expectancy: {trends['expectancy'].title()}\n\n"
        
        # Week vs Month comparison
        if weekly['total_trades'] > 0:
            weekly_daily = weekly['profit_sum'] / 7
            monthly_daily = monthly['profit_sum'] / 30
            daily_change = (weekly_daily - monthly_daily) / monthly_daily if monthly_daily != 0 else 0
            
            message += f"*🔥 Recent vs Historical*\n"
            message += f"7-day daily profit: {weekly_daily:.3%}\n"
            message += f"30-day daily profit: {monthly_daily:.3%}\n"
            message += f"Change: {daily_change:+.1%}\n\n"
    
    # Factor summary
    if factors:
        aggressive = [pair for pair, factor in factors.items() if factor > 1.2]
        conservative = [pair for pair, factor in factors.items() if factor < 0.8]
        
        message += f"*⚖️ Position Sizing Updates*\n"
        message += f"Total pairs: {len(factors)}\n"
        message += f"Avg factor: {sum(factors.values())/len(factors):.3f}\n"
        
        if aggressive:
            message += f"\n*🚀 Aggressive (>1.2):*\n"
            for pair in aggressive[:5]:  # Top 5
                message += f"{pair}: {factors[pair]:.3f}\n"
        
        if conservative:
            message += f"\n*🛡️ Conservative (<0.8):*\n"
            for pair in conservative[:5]:  # Top 5
                message += f"{pair}: {factors[pair]:.3f}\n"
    
    return message

def main():
    """Main execution flow with enhanced functionality"""
    parser = argparse.ArgumentParser(description='Enhanced FreqTrade Risk Management')
    parser.add_argument('--mode', choices=['adaptive', 'traditional'], default='adaptive',
                       help='Analysis mode: adaptive (30-day rolling) or traditional (all history)')
    parser.add_argument('--days', type=int, default=30,
                       help='Days to look back for adaptive mode')
    parser.add_argument('--no-telegram', action='store_true',
                       help='Skip Telegram notification')
    
    args = parser.parse_args()
    
    print(f"🚀 Starting Enhanced Risk Management at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {args.mode}")
    
    try:
        # Run enhanced workflow
        factors, trends, metrics_comparison = enhanced_risk_management_workflow(args.mode)
        
        if not factors:
            print("⚠️ No factors generated - insufficient trade data")
            return
        
        # Create and send Telegram report
        if not args.no_telegram:
            telegram_message = create_enhanced_telegram_report(factors, trends, metrics_comparison, args.mode)
            response = send_telegram_message(telegram_message)
            if response:
                print("✅ Telegram notification sent")
            else:
                print("⚠️ Failed to send Telegram notification")
        
        print(f"✅ Enhanced risk analysis completed successfully")
        print(f"   Generated factors for {len(factors)} pairs")
        
        if args.mode == 'adaptive':
            print(f"   Strategy trend: {trends.get('overall', 'unknown')}")
            
    except Exception as e:
        error_msg = f"❌ Error in risk management: {str(e)}"
        print(error_msg)
        if not args.no_telegram:
            send_telegram_message(f"*Risk Management Error*\n{error_msg}")

if __name__ == "__main__":
    main()  

