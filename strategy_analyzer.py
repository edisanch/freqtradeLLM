#!/usr/bin/env python3
"""
FreqTrade Strategy Performance Analyzer
Analyzes trading strategy performance between specific dates with detailed insights
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta
import argparse
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

# Configuration
CONFIG_FILE = "/home/stivi/freqtradeLLM/config.json"
DB_FILE = "/home/stivi/freqtradeLLM/tradesv3.dryrun.sqlite"
OUTPUT_DIR = "/home/stivi/freqtradeLLM/user_data/performance_analysis"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

class StrategyPerformanceAnalyzer:
    def __init__(self, start_date: str, end_date: str):
        self.start_date = start_date
        self.end_date = end_date
        self.trades = self.load_trades()
        
    def load_trades(self):
        """Load trades from database for the specified date range"""
        conn = sqlite3.connect(DB_FILE)
        
        # First, check what columns exist in the trades table
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(trades)")
        columns_info = cursor.fetchall()
        available_columns = [col[1] for col in columns_info]
        
        # Build query with only available columns
        base_columns = [
            "pair",
            "close_profit as profit_ratio",
            "open_date", 
            "close_date",
            "CAST((julianday(close_date) - julianday(open_date)) * 1440 AS INTEGER) as trade_duration",
            "open_rate",
            "close_rate", 
            "stake_amount",
            "exit_reason",
            "strategy"
        ]
        
        # Optional columns that might not exist in all FreqTrade versions
        optional_columns = {
            "max_rate": "max_rate",
            "min_rate": "min_rate", 
            "enter_tag": "enter_tag as tag",
            "buy_tag": "buy_tag",
            "sell_tag": "sell_tag",
            "exit_tag": "exit_tag",
            "fee_open": "fee_open",
            "fee_close": "fee_close",
            "is_open": "is_open",
            "leverage": "leverage",
            "amount": "amount",
            "open_order_id": "open_order_id",
            "close_order_id": "close_order_id"
        }
        
        # Add optional columns if they exist
        for col_name, col_query in optional_columns.items():
            if col_name in available_columns:
                base_columns.append(col_query)
        
        query = f"""
        SELECT 
            {', '.join(base_columns)}
        FROM trades
        WHERE close_date IS NOT NULL
        AND close_date >= ? 
        AND close_date <= ?
        ORDER BY close_date ASC
        """
        
        # Format dates for SQLite
        start_formatted = f"{self.start_date} 00:00:00"
        end_formatted = f"{self.end_date} 23:59:59"
        
        try:
            trades = pd.read_sql_query(query, conn, params=(start_formatted, end_formatted))
            conn.close()
            
            if trades.empty:
                print(f"No trades found between {self.start_date} and {self.end_date}")
                return trades
                
            # Convert date columns
            trades['open_date'] = pd.to_datetime(trades['open_date'])
            trades['close_date'] = pd.to_datetime(trades['close_date'])
            
            print(f"Loaded {len(trades)} trades between {self.start_date} and {self.end_date}")
            print(f"Available columns: {list(trades.columns)}")
            return trades
            
        except Exception as e:
            conn.close()
            print(f"Error loading trades: {e}")
            print("Available columns in database:")
            for col in available_columns:
                print(f"  - {col}")
            return pd.DataFrame()
    
    def calculate_comprehensive_metrics(self):
        """Calculate comprehensive performance metrics"""
        if self.trades.empty:
            return {}
            
        trades = self.trades.copy()
        
        # Basic performance metrics
        metrics = {
            'period': f"{self.start_date} to {self.end_date}",
            'total_trades': len(trades),
            'winning_trades': len(trades[trades['profit_ratio'] > 0]),
            'losing_trades': len(trades[trades['profit_ratio'] <= 0]),
            'win_rate': len(trades[trades['profit_ratio'] > 0]) / len(trades),
            'total_profit_pct': trades['profit_ratio'].sum() * 100,
            'avg_profit_pct': trades['profit_ratio'].mean() * 100,
            'median_profit_pct': trades['profit_ratio'].median() * 100,
            'best_trade_pct': trades['profit_ratio'].max() * 100,
            'worst_trade_pct': trades['profit_ratio'].min() * 100,
            'profit_std': trades['profit_ratio'].std() * 100,
        }
        
        # Advanced metrics
        metrics.update(self._calculate_risk_metrics(trades))
        metrics.update(self._calculate_time_metrics(trades))
        metrics.update(self._calculate_streak_metrics(trades))
        metrics.update(self._calculate_distribution_metrics(trades))
        
        return metrics
    
    def _calculate_risk_metrics(self, trades):
        """Calculate risk-adjusted metrics"""
        # Sharpe ratio (annualized)
        daily_returns = self._get_daily_returns(trades)
        if len(daily_returns) > 1:
            sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(365) if daily_returns.std() > 0 else 0
        else:
            sharpe = 0
            
        # Maximum drawdown
        cumulative = (1 + trades['profit_ratio']).cumprod()
        peak = cumulative.expanding().max()
        drawdown = (cumulative / peak) - 1
        max_drawdown = drawdown.min()
        
        # Profit factor
        gross_profit = trades.loc[trades['profit_ratio'] > 0, 'profit_ratio'].sum()
        gross_loss = abs(trades.loc[trades['profit_ratio'] < 0, 'profit_ratio'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Expectancy
        wins = trades[trades['profit_ratio'] > 0]
        losses = trades[trades['profit_ratio'] < 0]
        
        avg_win = wins['profit_ratio'].mean() if not wins.empty else 0
        avg_loss = losses['profit_ratio'].mean() if not losses.empty else 0
        win_rate = len(wins) / len(trades) if len(trades) > 0 else 0
        loss_rate = len(losses) / len(trades) if len(trades) > 0 else 0
        
        expectancy = (avg_win * win_rate) + (avg_loss * loss_rate)
        
        # Recovery factor
        recovery_factor = abs(trades['profit_ratio'].sum() / max_drawdown) if max_drawdown < 0 else float('inf')
        
        return {
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown * 100,
            'profit_factor': profit_factor,
            'expectancy': expectancy,
            'recovery_factor': recovery_factor,
            'avg_win_pct': avg_win * 100,
            'avg_loss_pct': avg_loss * 100,
            'gross_profit_pct': gross_profit * 100,
            'gross_loss_pct': gross_loss * 100,
        }
    
    def _calculate_time_metrics(self, trades):
        """Calculate time-based metrics"""
        # Trade duration statistics
        avg_duration = trades['trade_duration'].mean()
        median_duration = trades['trade_duration'].median()
        
        # Trades per day
        start = trades['close_date'].min().date()
        end = trades['close_date'].max().date()
        days = (end - start).days + 1
        trades_per_day = len(trades) / days if days > 0 else 0
        
        # Time-based win rates
        trades['hour'] = trades['close_date'].dt.hour
        trades['day_of_week'] = trades['close_date'].dt.day_name()
        
        hourly_performance = trades.groupby('hour').agg({
            'profit_ratio': ['count', 'mean', lambda x: (x > 0).mean()]
        }).round(4)
        
        daily_performance = trades.groupby('day_of_week').agg({
            'profit_ratio': ['count', 'mean', lambda x: (x > 0).mean()]
        }).round(4)
        
        return {
            'avg_trade_duration_minutes': avg_duration,
            'median_trade_duration_minutes': median_duration,
            'trades_per_day': trades_per_day,
            'total_days': days,
            'best_hour': hourly_performance['profit_ratio']['mean'].idxmax(),
            'worst_hour': hourly_performance['profit_ratio']['mean'].idxmin(),
            'best_day': daily_performance['profit_ratio']['mean'].idxmax(),
            'worst_day': daily_performance['profit_ratio']['mean'].idxmin(),
        }
    
    def _calculate_streak_metrics(self, trades):
        """Calculate winning/losing streak metrics"""
        if trades.empty:
            return {}
            
        # Create streak series
        trades_sorted = trades.sort_values('close_date')
        is_win = (trades_sorted['profit_ratio'] > 0).astype(int)
        
        # Calculate streaks
        streaks = []
        current_streak = 0
        current_type = None
        
        for win in is_win:
            if win == current_type:
                current_streak += 1
            else:
                if current_streak > 0:
                    streaks.append((current_type, current_streak))
                current_streak = 1
                current_type = win
        
        if current_streak > 0:
            streaks.append((current_type, current_streak))
        
        # Analyze streaks
        win_streaks = [length for is_win, length in streaks if is_win == 1]
        loss_streaks = [length for is_win, length in streaks if is_win == 0]
        
        return {
            'max_winning_streak': max(win_streaks) if win_streaks else 0,
            'max_losing_streak': max(loss_streaks) if loss_streaks else 0,
            'avg_winning_streak': np.mean(win_streaks) if win_streaks else 0,
            'avg_losing_streak': np.mean(loss_streaks) if loss_streaks else 0,
            'current_streak': current_streak if current_type else 0,
            'current_streak_type': 'winning' if current_type == 1 else 'losing' if current_type == 0 else 'none'
        }
    
    def _calculate_distribution_metrics(self, trades):
        """Calculate distribution and statistical metrics"""
        profits = trades['profit_ratio']
        
        # Statistical tests
        _, normality_p = stats.normaltest(profits)
        skewness = stats.skew(profits)
        kurtosis = stats.kurtosis(profits)
        
        # Percentiles
        percentiles = [5, 10, 25, 75, 90, 95]
        profit_percentiles = {f'p{p}': np.percentile(profits * 100, p) for p in percentiles}
        
        return {
            'normality_p_value': normality_p,
            'is_normal_distribution': normality_p > 0.05,
            'skewness': skewness,
            'kurtosis': kurtosis,
            **profit_percentiles
        }
    
    def _get_daily_returns(self, trades):
        """Calculate daily returns"""
        trades_daily = trades.groupby(trades['close_date'].dt.date)['profit_ratio'].sum()
        return trades_daily
    
    def analyze_by_pair(self):
        """Analyze performance by trading pair"""
        if self.trades.empty:
            return pd.DataFrame()
            
        pair_analysis = self.trades.groupby('pair').agg({
            'profit_ratio': ['count', 'mean', 'sum', 'std', 'min', 'max'],
            'trade_duration': ['mean', 'median'],
            'stake_amount': 'mean'
        }).round(4)
        
        # Flatten column names
        pair_analysis.columns = ['_'.join(col).strip() for col in pair_analysis.columns.values]
        pair_analysis = pair_analysis.reset_index()
        
        # Calculate additional metrics
        pair_wins = self.trades[self.trades['profit_ratio'] > 0].groupby('pair').size()
        pair_analysis['wins'] = pair_analysis['pair'].map(pair_wins).fillna(0).astype(int)
        pair_analysis['win_rate'] = pair_analysis['wins'] / pair_analysis['profit_ratio_count']
        
        # Calculate expectancy per pair
        pair_analysis['expectancy'] = pair_analysis.apply(
            lambda row: self._calculate_pair_expectancy(row['pair']), axis=1
        )
        
        # Calculate Sharpe ratio per pair
        pair_analysis['sharpe'] = pair_analysis.apply(
            lambda row: self._calculate_pair_sharpe(row['pair']), axis=1
        )
        
        return pair_analysis.sort_values('expectancy', ascending=False)
    
    def _calculate_pair_expectancy(self, pair):
        """Calculate expectancy for specific pair"""
        pair_trades = self.trades[self.trades['pair'] == pair]
        wins = pair_trades[pair_trades['profit_ratio'] > 0]
        losses = pair_trades[pair_trades['profit_ratio'] < 0]
        
        if len(pair_trades) == 0:
            return 0
            
        win_rate = len(wins) / len(pair_trades)
        loss_rate = len(losses) / len(pair_trades)
        avg_win = wins['profit_ratio'].mean() if not wins.empty else 0
        avg_loss = losses['profit_ratio'].mean() if not losses.empty else 0
        
        return (avg_win * win_rate) + (avg_loss * loss_rate)
    
    def _calculate_pair_sharpe(self, pair):
        """Calculate Sharpe ratio for specific pair"""
        pair_trades = self.trades[self.trades['pair'] == pair]
        if len(pair_trades) < 2:
            return 0
            
        returns = pair_trades['profit_ratio']
        return (returns.mean() / returns.std()) * np.sqrt(365) if returns.std() > 0 else 0
    
    def analyze_by_entry_exit(self):
        """Analyze performance by entry and exit strategies"""
        analysis = {}
        
        # Check what tag columns are available
        tag_columns = ['tag', 'enter_tag', 'buy_tag']
        available_tag_col = None
        
        for col in tag_columns:
            if col in self.trades.columns and not self.trades[col].isna().all():
                available_tag_col = col
                break
        
        # Entry tag analysis
        if available_tag_col:
            entry_analysis = self.trades.dropna(subset=[available_tag_col]).groupby(available_tag_col).agg({
                'profit_ratio': ['count', 'mean', 'sum', lambda x: (x > 0).mean()],
                'trade_duration': 'mean'
            }).round(4)
            entry_analysis.columns = ['trades', 'avg_profit', 'total_profit', 'win_rate', 'avg_duration']
            analysis['entry_tags'] = entry_analysis.reset_index()
            analysis['entry_tag_column'] = available_tag_col
    
        # Exit reason analysis
        if 'exit_reason' in self.trades.columns:
            exit_analysis = self.trades.groupby('exit_reason').agg({
                'profit_ratio': ['count', 'mean', 'sum', lambda x: (x > 0).mean()],
                'trade_duration': 'mean'
            }).round(4)
            exit_analysis.columns = ['trades', 'avg_profit', 'total_profit', 'win_rate', 'avg_duration']
            analysis['exit_reasons'] = exit_analysis.reset_index()
    
        return analysis
    
    def analyze_market_conditions(self):
        """Analyze performance under different market conditions"""
        if self.trades.empty:
            return {}
            
        # Load pair factors to understand market context
        try:
            with open('/home/stivi/freqtradeLLM/user_data/pair_factors.json', 'r') as f:
                pair_factors = json.load(f)
        except:
            pair_factors = {}
        
        # Categorize pairs by performance factors
        analysis = {}
        for pair in self.trades['pair'].unique():
            factor = pair_factors.get(pair, 1.0)
            if factor > 1.1:
                category = 'high_performing'
            elif factor < 0.9:
                category = 'low_performing'
            else:
                category = 'average_performing'
            
            if category not in analysis:
                analysis[category] = []
            analysis[category].append(pair)
        
        # Calculate performance by category
        performance_by_category = {}
        for category, pairs in analysis.items():
            category_trades = self.trades[self.trades['pair'].isin(pairs)]
            if not category_trades.empty:
                performance_by_category[category] = {
                    'trade_count': len(category_trades),
                    'avg_profit': category_trades['profit_ratio'].mean(),
                    'total_profit': category_trades['profit_ratio'].sum(),
                    'win_rate': (category_trades['profit_ratio'] > 0).mean(),
                    'pairs': pairs
                }
        
        return performance_by_category
    
    def create_visualizations(self):
        """Create comprehensive visualizations"""
        if self.trades.empty:
            print("No trades to visualize")
            return
            
        # Set up the plotting style
        try:
            plt.style.use('seaborn-v0_8')
        except:
            try:
                plt.style.use('seaborn')
            except:
                pass  # Use default style if seaborn not available
            
        fig = plt.figure(figsize=(20, 16))
        
        # 1. Cumulative Profit Chart
        trades_sorted = self.trades.sort_values('close_date')
        trades_sorted['cumulative_profit'] = (1 + trades_sorted['profit_ratio']).cumprod() - 1
        
        plt.subplot(3, 3, 1)
        plt.plot(trades_sorted['close_date'], trades_sorted['cumulative_profit'] * 100, linewidth=2)
        plt.title('Cumulative Profit Over Time', fontsize=14, fontweight='bold')
        plt.ylabel('Cumulative Profit (%)')
        plt.grid(True, alpha=0.3)
        
        # 2. Daily Profit Distribution
        daily_profits = self._get_daily_returns(self.trades)
        plt.subplot(3, 3, 2)
        plt.hist(daily_profits * 100, bins=20, alpha=0.7, edgecolor='black')
        plt.title('Daily Profit Distribution', fontsize=14, fontweight='bold')
        plt.xlabel('Daily Profit (%)')
        plt.ylabel('Frequency')
        plt.grid(True, alpha=0.3)
        
        # 3. Profit by Pair (Top 10)
        pair_analysis = self.analyze_by_pair()
        if not pair_analysis.empty:
            top_pairs = pair_analysis.nlargest(10, 'profit_ratio_sum')
            plt.subplot(3, 3, 3)
            bars = plt.bar(range(len(top_pairs)), top_pairs['profit_ratio_sum'] * 100)
            plt.title('Top 10 Pairs by Total Profit', fontsize=14, fontweight='bold')
            plt.ylabel('Total Profit (%)')
            plt.xticks(range(len(top_pairs)), top_pairs['pair'], rotation=45)
            
            # Color bars based on profit
            for i, bar in enumerate(bars):
                if top_pairs.iloc[i]['profit_ratio_sum'] > 0:
                    bar.set_color('green')
                else:
                    bar.set_color('red')
    
        # 4. Win Rate by Pair
        if not pair_analysis.empty:
            plt.subplot(3, 3, 4)
            plt.bar(range(len(top_pairs)), top_pairs['win_rate'] * 100, color='skyblue', edgecolor='black')
            plt.title('Win Rate by Top Pairs', fontsize=14, fontweight='bold')
            plt.ylabel('Win Rate (%)')
            plt.xticks(range(len(top_pairs)), top_pairs['pair'], rotation=45)
            plt.grid(True, alpha=0.3, axis='y')
        
        # 5. Trade Duration Distribution
        plt.subplot(3, 3, 5)
        plt.hist(self.trades['trade_duration'], bins=30, alpha=0.7, color='orange', edgecolor='black')
        plt.title('Trade Duration Distribution', fontsize=14, fontweight='bold')
        plt.xlabel('Duration (minutes)')
        plt.ylabel('Number of Trades')
        plt.grid(True, alpha=0.3)
        
        # 6. Profit vs Duration Scatter
        plt.subplot(3, 3, 6)
        colors = ['green' if x > 0 else 'red' for x in self.trades['profit_ratio']]
        plt.scatter(self.trades['trade_duration'], self.trades['profit_ratio'] * 100, 
                   c=colors, alpha=0.6)
        plt.title('Profit vs Trade Duration', fontsize=14, fontweight='bold')
        plt.xlabel('Duration (minutes)')
        plt.ylabel('Profit (%)')
        plt.grid(True, alpha=0.3)
        
        # 7. Rolling Win Rate
        window = max(10, len(self.trades) // 20)  # Adaptive window size
        trades_sorted['rolling_wins'] = (trades_sorted['profit_ratio'] > 0).rolling(window=window).mean()
        
        plt.subplot(3, 3, 7)
        plt.plot(trades_sorted['close_date'], trades_sorted['rolling_wins'] * 100, linewidth=2, color='purple')
        plt.title(f'Rolling Win Rate (Window: {window})', fontsize=14, fontweight='bold')
        plt.ylabel('Win Rate (%)')
        plt.grid(True, alpha=0.3)
        
        # 8. Exit Reason Analysis (only if data available)
        exit_analysis = self.analyze_by_entry_exit()
        if 'exit_reasons' in exit_analysis and not exit_analysis['exit_reasons'].empty:
            exit_data = exit_analysis['exit_reasons']
            plt.subplot(3, 3, 8)
            plt.pie(exit_data['trades'], labels=exit_data['exit_reason'], autopct='%1.1f%%')
            plt.title('Exit Reasons Distribution', fontsize=14, fontweight='bold')
        else:
            # Alternative plot if exit reasons not available
            plt.subplot(3, 3, 8)
            win_loss = [len(self.trades[self.trades['profit_ratio'] > 0]), 
                       len(self.trades[self.trades['profit_ratio'] <= 0])]
            plt.pie(win_loss, labels=['Wins', 'Losses'], autopct='%1.1f%%', colors=['green', 'red'])
            plt.title('Win/Loss Distribution', fontsize=14, fontweight='bold')
        
        # 9. Drawdown Chart
        peak = trades_sorted['cumulative_profit'].expanding().max()
        drawdown = (trades_sorted['cumulative_profit'] - peak) * 100
        
        plt.subplot(3, 3, 9)
        plt.fill_between(trades_sorted['close_date'], drawdown, 0, color='red', alpha=0.3)
        plt.plot(trades_sorted['close_date'], drawdown, color='red', linewidth=2)
        plt.title('Drawdown Over Time', fontsize=14, fontweight='bold')
        plt.ylabel('Drawdown (%)')
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save the plot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"strategy_analysis_{self.start_date}_to_{self.end_date}_{timestamp}.png"
        filepath = os.path.join(OUTPUT_DIR, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Visualizations saved to: {filepath}")
        return filepath
    
    def generate_detailed_report(self):
        """Generate comprehensive performance report"""
        report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'period': f"{self.start_date} to {self.end_date}",
            'overall_metrics': self.calculate_comprehensive_metrics(),
            'pair_analysis': self.analyze_by_pair().to_dict(orient='records') if not self.analyze_by_pair().empty else [],
            'entry_exit_analysis': self.analyze_by_entry_exit(),
            'market_conditions': self.analyze_market_conditions(),
        }
        
        # Save detailed report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"detailed_analysis_{self.start_date}_to_{self.end_date}_{timestamp}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=4, default=str)
        
        print(f"Detailed report saved to: {filepath}")
        return report, filepath
    
    def print_summary_report(self):
        """Print a formatted summary to console"""
        metrics = self.calculate_comprehensive_metrics()
        
        print("=" * 80)
        print(f"STRATEGY PERFORMANCE ANALYSIS: {metrics['period']}")
        print("=" * 80)
        
        print(f"\n📊 OVERALL PERFORMANCE")
        print(f"├─ Total Trades: {metrics['total_trades']}")
        print(f"├─ Win Rate: {metrics['win_rate']:.2%}")
        print(f"├─ Total Profit: {metrics['total_profit_pct']:.2f}%")
        print(f"├─ Average Profit: {metrics['avg_profit_pct']:.2f}%")
        print(f"├─ Best Trade: {metrics['best_trade_pct']:.2f}%")
        print(f"└─ Worst Trade: {metrics['worst_trade_pct']:.2f}%")
        
        print(f"\n📈 RISK METRICS")
        print(f"├─ Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"├─ Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        print(f"├─ Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"├─ Expectancy: {metrics['expectancy']:.4f}")
        print(f"└─ Recovery Factor: {metrics['recovery_factor']:.2f}")
        
        print(f"\n⏱️  TIME ANALYSIS")
        print(f"├─ Avg Trade Duration: {metrics['avg_trade_duration_minutes']:.1f} minutes")
        print(f"├─ Trades per Day: {metrics['trades_per_day']:.1f}")
        print(f"├─ Best Trading Hour: {metrics['best_hour']:02d}:00")
        print(f"└─ Best Trading Day: {metrics['best_day']}")
        
        print(f"\n🔥 STREAKS")
        print(f"├─ Max Winning Streak: {metrics['max_winning_streak']}")
        print(f"├─ Max Losing Streak: {metrics['max_losing_streak']}")
        print(f"└─ Current Streak: {metrics['current_streak']} ({metrics['current_streak_type']})")
        
        # Top performing pairs
        pair_analysis = self.analyze_by_pair()
        if not pair_analysis.empty:
            print(f"\n🏆 TOP 5 PERFORMING PAIRS")
            top_pairs = pair_analysis.nlargest(5, 'expectancy')
            for i, (_, row) in enumerate(top_pairs.iterrows(), 1):
                print(f"{i}. {row['pair']}: {row['profit_ratio_sum']*100:.2f}% total, {row['win_rate']*100:.1f}% win rate ({int(row['profit_ratio_count'])} trades)")
        
        print("=" * 80)

def main():
    """Main execution with command line arguments"""
    parser = argparse.ArgumentParser(description='Analyze FreqTrade strategy performance between dates')
    parser.add_argument('start_date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('end_date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--charts', action='store_true', help='Generate visualization charts')
    parser.add_argument('--detailed', action='store_true', help='Generate detailed JSON report')
    
    # If no arguments provided, use default dates (May 5-13, 2025)
    import sys
    if len(sys.argv) == 1:
        start_date = "2025-05-05"
        end_date = "2025-05-13"
        generate_charts = True
        generate_detailed = True
        print(f"No arguments provided. Using default period: {start_date} to {end_date}")
    else:
        args = parser.parse_args()
        start_date = args.start_date
        end_date = args.end_date
        generate_charts = args.charts
        generate_detailed = args.detailed
    
    # Validate dates
    try:
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        print("Error: Invalid date format. Use YYYY-MM-DD")
        return
    
    # Create analyzer and run analysis
    analyzer = StrategyPerformanceAnalyzer(start_date, end_date)
    
    if analyzer.trades.empty:
        print("No trades found for the specified period.")
        return
    
    # Print summary
    analyzer.print_summary_report()
    
    # Generate charts if requested
    if generate_charts:
        analyzer.create_visualizations()
    
    # Generate detailed report if requested
    if generate_detailed:
        analyzer.generate_detailed_report()

if __name__ == "__main__":
    main()