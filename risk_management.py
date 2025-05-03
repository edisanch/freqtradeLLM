#!/usr/bin/env python3
"""
FreqTrade Risk Management Script
This script analyzes trading performance and provides risk management insights
Run weekly to reassess strategy performance and make data-driven adjustments
"""
import json
import os
import sqlite3
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

def get_trades_from_db():
    """Extract trades from SQLite database"""
    conn = sqlite3.connect(DB_FILE)
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

def calculate_metrics(trades):
    """Calculate key performance metrics"""
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
        
    pair_metrics = trades.groupby('pair').agg({
        'profit_ratio': ['count', 'mean', 'sum', 'std'],
        'trade_duration': 'mean'
    }).reset_index()
    
    pair_metrics.columns = ['pair', 'trade_count', 'avg_profit', 'total_profit', 'profit_std', 'avg_duration']
    
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

def analyze_by_tag(trades):
    """Analyze performance by strategy tag"""
    if trades.empty or 'tag' not in trades.columns:
        return pd.DataFrame()
        
    # Filter only trades with tags
    tagged_trades = trades.dropna(subset=['tag'])
    
    if tagged_trades.empty:
        return pd.DataFrame()
        
    tag_metrics = tagged_trades.groupby('tag').agg({
        'profit_ratio': ['count', 'mean', 'sum'],
        'trade_duration': 'mean'
    }).reset_index()
    
    tag_metrics.columns = ['tag', 'trade_count', 'avg_profit', 'total_profit', 'avg_duration']
    
    # Calculate win rate per tag
    win_counts = tagged_trades[tagged_trades['profit_ratio'] > 0].groupby('tag').size()
    tag_metrics['win_count'] = tag_metrics['tag'].map(win_counts).fillna(0).astype(int)
    tag_metrics['win_rate'] = tag_metrics['win_count'] / tag_metrics['trade_count']
    
    return tag_metrics.sort_values('total_profit', ascending=False)

def analyze_recent_performance(trades):
    """Analyze recent performance vs historical"""
    if trades.empty:
        return {}
        
    trades['close_date'] = pd.to_datetime(trades['close_date'])
    
    # Define time periods
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    recent_week = trades[trades['close_date'] > week_ago]
    recent_month = trades[trades['close_date'] > month_ago]
    older_trades = trades[trades['close_date'] <= month_ago]
    
    metrics = {
        'recent_week': calculate_metrics(recent_week) if not recent_week.empty else None,
        'recent_month': calculate_metrics(recent_month) if not recent_month.empty else None,
        'historical': calculate_metrics(older_trades) if not older_trades.empty else None
    }
    
    return metrics

def generate_position_size_recommendations(pair_metrics, base_position_size=0.05):
    """Generate position sizing recommendations based on pair performance"""
    if pair_metrics.empty:
        return pd.DataFrame()
    
    # Calculate position size based on multiple factors
    recommendations = pair_metrics[['pair', 'expectancy', 'win_rate', 'avg_profit', 'profit_std', 'total_profit', 'trade_count']].copy()
    
    # Add absolute profit to consider actual dollar impact
    # This ensures pairs with large absolute losses get properly penalized
    recommendations['abs_profit'] = recommendations['total_profit'].abs()
    max_abs_profit = recommendations['abs_profit'].max()
    
    # Normalize expectancy (min-max scaling)
    min_exp = recommendations['expectancy'].min()
    max_exp = recommendations['expectancy'].max()
    
    if max_exp == min_exp:  # Avoid division by zero
        recommendations['expectancy_factor'] = 1.0
    else:
        recommendations['expectancy_factor'] = (recommendations['expectancy'] - min_exp) / (max_exp - min_exp)
        
    # Calculate profitability factor based on both expectancy and total profit
    recommendations['profitability_score'] = recommendations.apply(
        lambda row: calculate_profitability_score(
            row['expectancy_factor'], 
            row['total_profit'], 
            row['trade_count'],
            max_abs_profit
        ), 
        axis=1
    )
    
    # Scale between 0.5 and 1.5 (adjusted from original range)
    min_score = recommendations['profitability_score'].min()
    max_score = recommendations['profitability_score'].max()
    
    if max_score == min_score:
        recommendations['position_factor'] = 1.0
    else:
        recommendations['position_factor'] = 0.5 + (recommendations['profitability_score'] - min_score) / (max_score - min_score)
    
    # Special handling for high-volume poorly performing pairs
    # If a pair has significant negative total profit and many trades, limit its factor
    recommendations['position_factor'] = recommendations.apply(
        lambda row: min(row['position_factor'], 0.7) if (row['total_profit'] < -10.0 and row['trade_count'] > 10) else row['position_factor'],
        axis=1
    )
    
    # Calculate position size
    recommendations['recommended_position'] = base_position_size * recommendations['position_factor']
    
    # Add risk adjustment based on volatility (profit_std)
    # Higher volatility = lower position size
    if recommendations['profit_std'].max() > 0:
        volatility_factor = 1 - (recommendations['profit_std'] / recommendations['profit_std'].max() * 0.5)
        recommendations['recommended_position'] *= volatility_factor
    
    return recommendations[['pair', 'recommended_position', 'position_factor', 'total_profit', 'trade_count']]

def calculate_profitability_score(expectancy_factor, total_profit, trade_count, max_abs_profit):
    """
    Calculate a comprehensive profitability score that considers:
    - Expectancy (win rate * avg win - loss rate * avg loss)
    - Total profit/loss in absolute dollars
    - Number of trades (statistical significance)
    
    Returns a score that penalizes pairs with large absolute losses and high trade counts
    """
    # Base score from expectancy factor (0-1 range)
    base_score = expectancy_factor
    
    # Weight for the total profit component - pairs with significant total profit/loss should be weighted more
    profit_significance = min(1.0, trade_count / 10)  # Maxes out at 10 trades
    
    # Calculate profit factor - negative impact increases with more trades and larger losses
    profit_factor = 0
    if total_profit < 0:
        # For losing pairs, create stronger penalty based on loss amount and trade count
        loss_severity = abs(total_profit) / max_abs_profit if max_abs_profit > 0 else 0
        profit_factor = -loss_severity * profit_significance
    else:
        # For winning pairs, boost based on profit and trade count
        profit_factor = (total_profit / max_abs_profit) * profit_significance if max_abs_profit > 0 else 0
    
    # Combine factors - expectancy gets 60% weight, actual profit gets 40% weight
    return base_score * 0.6 + profit_factor * 0.4

def generate_risk_report(trades):
    """Generate comprehensive risk report"""
    report_date = datetime.now().strftime("%Y-%m-%d")
    
    # Calculate overall metrics
    overall_metrics = calculate_metrics(trades)
    
    # Analyze by pair
    pair_metrics = analyze_by_pair(trades)
    
    # Analyze by tag
    tag_metrics = analyze_by_tag(trades)
    
    # Recent performance
    time_comparison = analyze_recent_performance(trades)
    
    # Generate position sizing recommendations
    position_recommendations = generate_position_size_recommendations(pair_metrics)
    
    # Create report
    report = {
        'report_date': report_date,
        'overall_metrics': overall_metrics,
        'pair_metrics': pair_metrics.to_dict(orient='records') if not pair_metrics.empty else [],
        'tag_metrics': tag_metrics.to_dict(orient='records') if not tag_metrics.empty else [],
        'time_comparison': time_comparison,
        'position_recommendations': position_recommendations.to_dict(orient='records') if not position_recommendations.empty else []
    }
    
    # Save report
    report_path = os.path.join(OUTPUT_DIR, f"risk_report_{report_date}.json")
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=4, default=str)
    
    # Save pair factors to be loaded by the strategy
    if not position_recommendations.empty:
        # Convert to a simple dictionary format for the strategy
        pair_factors = {}
        for _, row in position_recommendations.iterrows():
            # Normalize factors around 1.0
            # Use position_factor as it's already normalized in a good range (0.5 to 1.5)
            pair_factors[row['pair']] = float(row['position_factor'])
        
        # Save factors to a file that can be loaded by the strategy
        factors_path = '/home/stivi/freqtradeLLM/user_data/pair_factors.json'
        with open(factors_path, 'w') as f:
            json.dump(pair_factors, f, indent=4)
        print(f"Pair factors saved to {factors_path}")
    
    return report, report_path

def create_visualizations(trades, report, output_dir):
    """Create visualizations for the risk report"""
    if trades.empty:
        return

    # Prepare data
    trades['close_date'] = pd.to_datetime(trades['close_date'])
    trades = trades.sort_values('close_date')
    trades['cumulative_profit'] = (1 + trades['profit_ratio']).cumprod() - 1
    
    # 1. Cumulative profit over time
    plt.figure(figsize=(12, 6))
    plt.plot(trades['close_date'], trades['cumulative_profit'] * 100)
    plt.title('Cumulative Profit Over Time (%)')
    plt.xlabel('Date')
    plt.ylabel('Cumulative Profit %')
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'cumulative_profit.png'))
    
    # 2. Win rate by pair (top 10)
    if not report['pair_metrics']:
        return

    pair_df = pd.DataFrame(report['pair_metrics'])
    if len(pair_df) > 10:
        pair_df = pair_df.nlargest(10, 'trade_count')
    
    plt.figure(figsize=(12, 6))
    plt.bar(pair_df['pair'], pair_df['win_rate'] * 100)
    plt.title('Win Rate by Pair (%)')
    plt.xlabel('Pair')
    plt.ylabel('Win Rate %')
    plt.xticks(rotation=45)
    plt.grid(True, axis='y')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'win_rate_by_pair.png'))
    
    # 3. Profit histogram
    plt.figure(figsize=(12, 6))
    plt.hist(trades['profit_ratio'] * 100, bins=30, alpha=0.7)
    plt.title('Profit Distribution (%)')
    plt.xlabel('Profit %')
    plt.ylabel('Number of Trades')
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'profit_histogram.png'))
    
    # 4. Recommended position sizing
    if 'position_recommendations' in report and report['position_recommendations']:
        pos_df = pd.DataFrame(report['position_recommendations'])
        if len(pos_df) > 10:
            pos_df = pos_df.nlargest(10, 'recommended_position')
        
        plt.figure(figsize=(12, 6))
        plt.bar(pos_df['pair'], pos_df['recommended_position'] * 100)
        plt.title('Recommended Position Size by Pair (% of Portfolio)')
        plt.xlabel('Pair')
        plt.ylabel('Position Size %')
        plt.xticks(rotation=45)
        plt.grid(True, axis='y')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'position_sizing.png'))
    
    plt.close('all')

def format_telegram_report(report):
    """Format a concise version of the report for Telegram"""
    metrics = report['overall_metrics']
    
    # Format overall metrics
    message = f"*FreqTrade Risk Management Report*\n"
    message += f"Date: {report['report_date']}\n\n"
    
    message += f"*Overall Performance*\n"
    message += f"Total Trades: {metrics['total_trades']}\n"
    message += f"Win Rate: {metrics['win_rate']:.2%}\n"
    message += f"Profit Sum: {metrics['profit_sum']:.2%}\n"
    message += f"Expectancy: {metrics['expectancy']:.4f}\n"
    message += f"Profit Factor: {metrics['profit_factor']:.2f}\n"
    message += f"Max Drawdown: {abs(metrics['max_drawdown']):.2%}\n\n"
    
    # Add top 3 and bottom 3 pairs
    if report['pair_metrics']:
        pair_df = pd.DataFrame(report['pair_metrics'])
        
        message += "*Top 3 Pairs*\n"
        top_pairs = pair_df.nlargest(3, 'expectancy')
        for _, row in top_pairs.iterrows():
            message += f"{row['pair']}: {row['avg_profit']:.2%} ({row['trade_count']} trades)\n"
        
        message += "\n*Bottom 3 Pairs*\n"
        bottom_pairs = pair_df.nsmallest(3, 'expectancy')
        for _, row in bottom_pairs.iterrows():
            message += f"{row['pair']}: {row['avg_profit']:.2%} ({row['trade_count']} trades)\n"
    
    # Add tag performance if available
    if report['tag_metrics']:
        tag_df = pd.DataFrame(report['tag_metrics'])
        
        message += "\n*Strategy Tags*\n"
        for _, row in tag_df.iterrows():
            message += f"{row['tag']}: {row['avg_profit']:.2%} win rate: {row['win_rate']:.2%}\n"
    
    # Add recent vs historical comparison
    time_comp = report['time_comparison']
    if time_comp.get('recent_week') and time_comp.get('historical'):
        recent = time_comp['recent_week']
        hist = time_comp['historical']
        
        change = (recent['win_rate'] - hist['win_rate']) / hist['win_rate'] if hist['win_rate'] else float('inf')
        
        message += f"\n*Recent Performance (7d)*\n"
        message += f"Win Rate: {recent['win_rate']:.2%} ({change:+.1%} vs historical)\n"
    
    message += f"\nDetailed report available in: risk_report_{report['report_date']}.json"
    
    return message

def main():
    """Main execution flow"""
    print(f"Starting risk analysis at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get trades
    trades = get_trades_from_db()
    
    if trades.empty:
        print("No closed trades found in database")
        return
    
    print(f"Analyzing {len(trades)} trades...")
    
    # Generate report
    report, report_path = generate_risk_report(trades)
    
    # Create visualizations
    create_visualizations(trades, report, OUTPUT_DIR)
    
    # Send summary to Telegram
    telegram_message = format_telegram_report(report)
    send_telegram_message(telegram_message)
    
    print(f"Risk analysis completed. Report saved to {report_path}")
    print(f"Visualizations saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()