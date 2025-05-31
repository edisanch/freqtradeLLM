#!/usr/bin/env python3
"""
UltimateCompEdgeStrategy Diagnostic Tool
Analyzes why the strategy is generating 0 trades and provides optimization recommendations.
"""

import pandas as pd
import numpy as np
import talib.abstract as ta
from pathlib import Path
import json
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, time
import warnings
warnings.filterwarnings('ignore')

# Add user_data/strategies to Python path for imports
import sys
sys.path.insert(0, '/home/stivi/freqtradeLLM/user_data/strategies')

from UltimateCompEdgeStrategy import UltimateCompEdgeStrategy

class StrategyDiagnostic:
    def __init__(self, data_path='/home/stivi/freqtradeLLM/user_data/data/binance'):
        self.data_path = Path(data_path)
        self.strategy = UltimateCompEdgeStrategy()
        
    def load_sample_data(self):
        """Load sample data for analysis"""
        # Look for available data files
        json_files = list(self.data_path.rglob("*.json"))
        if not json_files:
            print("No data files found. Creating synthetic data for analysis.")
            return self.create_synthetic_data()
        
        # Use the first available pair
        data_file = json_files[0]
        print(f"Loading data from: {data_file}")
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        # Convert to DataFrame
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')
        
        # Convert to numeric
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def create_synthetic_data(self):
        """Create synthetic data for testing"""
        print("Creating synthetic market data for analysis...")
        
        # Generate 1000 candles of synthetic data
        np.random.seed(42)
        dates = pd.date_range('2024-11-01', periods=1000, freq='5T')
        
        # Create realistic OHLCV data
        returns = np.random.normal(0, 0.01, 1000)
        price = 100
        prices = []
        
        for ret in returns:
            price *= (1 + ret)
            prices.append(price)
        
        df = pd.DataFrame(index=dates)
        df['close'] = prices
        df['open'] = df['close'].shift(1).fillna(df['close'])
        df['high'] = df[['open', 'close']].max(axis=1) * (1 + np.random.uniform(0, 0.02, len(df)))
        df['low'] = df[['open', 'close']].min(axis=1) * (1 - np.random.uniform(0, 0.02, len(df)))
        df['volume'] = np.random.uniform(1000, 10000, len(df))
        
        return df
    
    def analyze_indicators(self, df):
        """Analyze strategy indicators"""
        print("\n" + "="*60)
        print("INDICATOR ANALYSIS")
        print("="*60)
        
        # Populate indicators using strategy method
        df_analyzed = self.strategy.populate_indicators(df.copy(), {'pair': 'TEST/USDT'})
        
        # Check for NaN values
        nan_cols = df_analyzed.columns[df_analyzed.isna().any()].tolist()
        if nan_cols:
            print(f"⚠️  WARNING: NaN values found in indicators: {nan_cols}")
            print(f"   First {self.strategy.startup_candle_count} candles may have NaN values")
        
        # Analyze key indicators
        recent_data = df_analyzed.tail(100)  # Last 100 candles
        
        print(f"\n📊 INDICATOR STATISTICS (Last 100 candles):")
        print(f"   EMA Fast ({self.strategy.ema_fast.value}): {recent_data['ema_fast'].mean():.2f} ± {recent_data['ema_fast'].std():.2f}")
        print(f"   EMA Slow ({self.strategy.ema_slow.value}): {recent_data['ema_slow'].mean():.2f} ± {recent_data['ema_slow'].std():.2f}")
        print(f"   RSI ({self.strategy.rsi_period.value}): {recent_data['rsi'].mean():.2f} ± {recent_data['rsi'].std():.2f}")
        print(f"   ADX ({self.strategy.adx_period.value}): {recent_data['adx'].mean():.2f} ± {recent_data['adx'].std():.2f}")
        print(f"   BB Width: {recent_data['bb_width'].mean():.4f} ± {recent_data['bb_width'].std():.4f}")
        print(f"   ATR Norm: {recent_data['atr_norm'].mean():.4f} ± {recent_data['atr_norm'].std():.4f}")
        print(f"   Supertrend: Uptrend {(recent_data['supertrend'] == 1).sum()}/100 candles")
        
        return df_analyzed
    
    def analyze_entry_conditions(self, df_analyzed):
        """Analyze individual entry conditions"""
        print("\n" + "="*60)
        print("ENTRY CONDITIONS ANALYSIS")
        print("="*60)
        
        recent_data = df_analyzed.tail(500)  # Last 500 candles for analysis
        
        # Individual conditions
        conditions = {
            'trend_filter': recent_data['close'] > recent_data['ema_slow'],
            'adx_filter': recent_data['adx'] > self.strategy.adx_threshold.value,
            'rsi_range': (recent_data['rsi'] > self.strategy.rsi_buy_min.value) & 
                        (recent_data['rsi'] < self.strategy.rsi_buy_max.value),
            'bb_buy': recent_data['close'] < (recent_data['bb_lower'] * 1.01),
            'vwap_buy': recent_data['close'] > recent_data['vwap'],
            'supertrend_filter': recent_data['supertrend'] == 1,
            'volume_filter': recent_data['volume'] > 0,
            'volatility_trending': (recent_data['bb_width'] > self.strategy.regime_bb_width_threshold.value) | 
                                 (recent_data['atr_norm'] > self.strategy.regime_atr_threshold.value)
        }
        
        print(f"📋 CONDITION PASS RATES (Last 500 candles):")
        for name, condition in conditions.items():
            pass_rate = condition.sum() / len(condition) * 100
            print(f"   {name:<20}: {pass_rate:5.1f}% ({condition.sum()}/{len(condition)})")
        
        # Combined conditions analysis
        bb_or_vwap = conditions['bb_buy'] | conditions['vwap_buy']
        print(f"   {'bb_buy OR vwap_buy':<20}: {bb_or_vwap.sum() / len(bb_or_vwap) * 100:5.1f}% ({bb_or_vwap.sum()}/{len(bb_or_vwap)})")
        
        # Trending market entry conditions
        trending_conditions = (
            conditions['trend_filter'] & 
            conditions['adx_filter'] & 
            conditions['rsi_range'] & 
            bb_or_vwap & 
            conditions['supertrend_filter'] & 
            conditions['volume_filter'] & 
            conditions['volatility_trending']
        )
        
        # Ranging market entry conditions
        ranging_conditions = (
            conditions['bb_buy'] & 
            (recent_data['rsi'] < (self.strategy.rsi_buy_min.value + 5)) & 
            (~conditions['volatility_trending']) & 
            conditions['volume_filter']
        )
        
        total_entries = trending_conditions | ranging_conditions
        
        print(f"\n🎯 COMBINED CONDITIONS:")
        print(f"   Trending Entry: {trending_conditions.sum()}/{len(trending_conditions)} ({trending_conditions.sum()/len(trending_conditions)*100:.1f}%)")
        print(f"   Ranging Entry:  {ranging_conditions.sum()}/{len(ranging_conditions)} ({ranging_conditions.sum()/len(ranging_conditions)*100:.1f}%)")
        print(f"   Total Entries:  {total_entries.sum()}/{len(total_entries)} ({total_entries.sum()/len(total_entries)*100:.1f}%)")
        
        return conditions, total_entries
    
    def suggest_optimizations(self, conditions, df_analyzed):
        """Suggest parameter optimizations"""
        print("\n" + "="*60)
        print("OPTIMIZATION RECOMMENDATIONS")
        print("="*60)
        
        recent_data = df_analyzed.tail(500)
        
        # Analyze current parameter effectiveness
        print("🔧 PARAMETER ANALYSIS:")
        
        # ADX threshold
        adx_values = recent_data['adx']
        adx_percentiles = np.percentile(adx_values.dropna(), [25, 50, 75, 90])
        current_adx = self.strategy.adx_threshold.value
        print(f"   ADX Threshold: Current={current_adx}, Market=[P25:{adx_percentiles[0]:.1f}, P50:{adx_percentiles[1]:.1f}, P75:{adx_percentiles[2]:.1f}, P90:{adx_percentiles[3]:.1f}]")
        if current_adx > adx_percentiles[2]:
            print(f"   ⚠️  ADX threshold too high! Try reducing to {adx_percentiles[1]:.0f}-{adx_percentiles[2]:.0f}")
        
        # RSI range
        rsi_values = recent_data['rsi']
        rsi_percentiles = np.percentile(rsi_values.dropna(), [10, 25, 50, 75, 90])
        current_rsi_min = self.strategy.rsi_buy_min.value
        current_rsi_max = self.strategy.rsi_buy_max.value
        print(f"   RSI Range: Current=[{current_rsi_min}-{current_rsi_max}], Market=[P10:{rsi_percentiles[0]:.1f}, P25:{rsi_percentiles[1]:.1f}, P50:{rsi_percentiles[2]:.1f}, P75:{rsi_percentiles[3]:.1f}, P90:{rsi_percentiles[4]:.1f}]")
        
        # BB width analysis
        bb_width_values = recent_data['bb_width']
        bb_width_percentiles = np.percentile(bb_width_values.dropna(), [25, 50, 75, 90])
        current_bb_threshold = self.strategy.regime_bb_width_threshold.value
        print(f"   BB Width Threshold: Current={current_bb_threshold:.3f}, Market=[P25:{bb_width_percentiles[0]:.3f}, P50:{bb_width_percentiles[1]:.3f}, P75:{bb_width_percentiles[2]:.3f}]")
        
        # ATR norm analysis
        atr_norm_values = recent_data['atr_norm']
        atr_norm_percentiles = np.percentile(atr_norm_values.dropna(), [25, 50, 75, 90])
        current_atr_threshold = self.strategy.regime_atr_threshold.value
        print(f"   ATR Norm Threshold: Current={current_atr_threshold:.3f}, Market=[P25:{atr_norm_percentiles[0]:.3f}, P50:{atr_norm_percentiles[1]:.3f}, P75:{atr_norm_percentiles[2]:.3f}]")
        
        print(f"\n💡 SPECIFIC RECOMMENDATIONS:")
        
        # Most restrictive conditions
        condition_pass_rates = {
            'ADX > threshold': conditions['adx_filter'].mean(),
            'RSI in range': conditions['rsi_range'].mean(),
            'Supertrend uptrend': conditions['supertrend_filter'].mean(),
            'BB/VWAP condition': (conditions['bb_buy'] | conditions['vwap_buy']).mean()
        }
        
        sorted_conditions = sorted(condition_pass_rates.items(), key=lambda x: x[1])
        
        print(f"   Most restrictive conditions (limiting trades):")
        for i, (name, rate) in enumerate(sorted_conditions[:3]):
            print(f"   {i+1}. {name}: {rate*100:.1f}% pass rate")
        
        # Specific suggestions
        if condition_pass_rates['ADX > threshold'] < 0.3:
            suggested_adx = max(15, int(adx_percentiles[1]))
            print(f"   🎯 Reduce ADX threshold from {current_adx} to {suggested_adx}")
        
        if condition_pass_rates['RSI in range'] < 0.4:
            print(f"   🎯 Widen RSI range: try [{int(rsi_percentiles[1])}-{int(rsi_percentiles[3])}] instead of [{current_rsi_min}-{current_rsi_max}]")
        
        if condition_pass_rates['Supertrend uptrend'] < 0.4:
            print(f"   🎯 Consider disabling Supertrend filter (set use_supertrend = False)")
        
        # Alternative configuration
        print(f"\n⚙️  SUGGESTED PARAMETER VALUES:")
        print(f"   adx_threshold: {max(15, int(adx_percentiles[1]))}")
        print(f"   rsi_buy_min: {max(20, int(rsi_percentiles[1]) - 5)}")
        print(f"   rsi_buy_max: {min(65, int(rsi_percentiles[3]) + 5)}")
        print(f"   bb_width_threshold: {bb_width_percentiles[1]:.3f}")
        print(f"   atr_threshold: {atr_norm_percentiles[1]:.3f}")
        print(f"   use_supertrend: {condition_pass_rates['Supertrend uptrend'] > 0.4}")
    
    def create_visualization(self, df_analyzed, total_entries):
        """Create diagnostic visualizations"""
        try:
            plt.style.use('seaborn-v0_8')
        except:
            plt.style.use('default')
        
        fig, axes = plt.subplots(3, 2, figsize=(15, 12))
        fig.suptitle('UltimateCompEdgeStrategy Diagnostic Analysis', fontsize=16, fontweight='bold')
        
        recent_data = df_analyzed.tail(200)
        entry_points = recent_data[total_entries.tail(200)]
        
        # Price and EMAs
        ax = axes[0, 0]
        ax.plot(recent_data.index, recent_data['close'], label='Close', linewidth=1.5)
        ax.plot(recent_data.index, recent_data['ema_fast'], label=f'EMA Fast ({self.strategy.ema_fast.value})', alpha=0.7)
        ax.plot(recent_data.index, recent_data['ema_slow'], label=f'EMA Slow ({self.strategy.ema_slow.value})', alpha=0.7)
        if len(entry_points) > 0:
            ax.scatter(entry_points.index, entry_points['close'], color='green', s=50, label='Entry Signals', zorder=5)
        ax.set_title('Price Action & Entry Signals')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # RSI
        ax = axes[0, 1]
        ax.plot(recent_data.index, recent_data['rsi'], label='RSI')
        ax.axhline(self.strategy.rsi_buy_min.value, color='green', linestyle='--', alpha=0.7, label='Buy Min')
        ax.axhline(self.strategy.rsi_buy_max.value, color='red', linestyle='--', alpha=0.7, label='Buy Max')
        ax.axhline(self.strategy.rsi_sell.value, color='red', linestyle='-', alpha=0.7, label='Sell')
        ax.set_title('RSI Levels')
        ax.set_ylabel('RSI')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Bollinger Bands
        ax = axes[1, 0]
        ax.plot(recent_data.index, recent_data['close'], label='Close', linewidth=1.5)
        ax.plot(recent_data.index, recent_data['bb_upper'], label='BB Upper', alpha=0.7)
        ax.plot(recent_data.index, recent_data['bb_middle'], label='BB Middle', alpha=0.7)
        ax.plot(recent_data.index, recent_data['bb_lower'], label='BB Lower', alpha=0.7)
        ax.plot(recent_data.index, recent_data['vwap'], label='VWAP', alpha=0.7)
        ax.fill_between(recent_data.index, recent_data['bb_lower'], recent_data['bb_upper'], alpha=0.1)
        ax.set_title('Bollinger Bands & VWAP')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # ADX and Supertrend
        ax = axes[1, 1]
        ax.plot(recent_data.index, recent_data['adx'], label='ADX', color='purple')
        ax.axhline(self.strategy.adx_threshold.value, color='purple', linestyle='--', alpha=0.7, label='ADX Threshold')
        ax2 = ax.twinx()
        colors = ['red' if x == -1 else 'green' for x in recent_data['supertrend']]
        ax2.scatter(recent_data.index, recent_data['supertrend'], c=colors, alpha=0.6, s=20, label='Supertrend')
        ax.set_title('ADX & Supertrend')
        ax.set_ylabel('ADX')
        ax2.set_ylabel('Supertrend')
        ax.legend(loc='upper left')
        ax2.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        # Volatility Regime
        ax = axes[2, 0]
        ax.plot(recent_data.index, recent_data['bb_width'], label='BB Width')
        ax.axhline(self.strategy.regime_bb_width_threshold.value, color='blue', linestyle='--', alpha=0.7, label='BB Width Threshold')
        ax2 = ax.twinx()
        ax2.plot(recent_data.index, recent_data['atr_norm'], label='ATR Norm', color='orange')
        ax2.axhline(self.strategy.regime_atr_threshold.value, color='orange', linestyle='--', alpha=0.7, label='ATR Threshold')
        ax.set_title('Volatility Regime Analysis')
        ax.set_ylabel('BB Width')
        ax2.set_ylabel('ATR Norm')
        ax.legend(loc='upper left')
        ax2.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        # Entry Condition Heatmap
        ax = axes[2, 1]
        condition_data = {
            'Trend': (recent_data['close'] > recent_data['ema_slow']).astype(int),
            'ADX': (recent_data['adx'] > self.strategy.adx_threshold.value).astype(int),
            'RSI': ((recent_data['rsi'] > self.strategy.rsi_buy_min.value) & 
                   (recent_data['rsi'] < self.strategy.rsi_buy_max.value)).astype(int),
            'BB/VWAP': ((recent_data['close'] < recent_data['bb_lower'] * 1.01) | 
                       (recent_data['close'] > recent_data['vwap'])).astype(int),
            'SuperT': (recent_data['supertrend'] == 1).astype(int),
        }
        
        condition_df = pd.DataFrame(condition_data, index=recent_data.index)
        # Sample every 10th row for readability
        sampled_df = condition_df.iloc[::10, :]
        
        sns.heatmap(sampled_df.T, cmap='RdYlGn', cbar_kws={'label': 'Condition Met'}, 
                   ax=ax, xticklabels=20, yticklabels=True)
        ax.set_title('Entry Conditions Heatmap (Sampled)')
        ax.set_xlabel('Time')
        
        plt.tight_layout()
        
        # Save the plot
        output_path = '/home/stivi/freqtradeLLM/ultimate_strategy_diagnostic.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"\n📊 Diagnostic chart saved to: {output_path}")
        plt.close()
    
    def run_full_analysis(self):
        """Run complete diagnostic analysis"""
        print("🔍 ULTIMATE COMP EDGE STRATEGY DIAGNOSTIC")
        print("="*60)
        
        # Load data
        df = self.load_sample_data()
        print(f"📈 Loaded {len(df)} candles for analysis")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")
        
        # Analyze indicators
        df_analyzed = self.analyze_indicators(df)
        
        # Analyze entry conditions
        conditions, total_entries = self.analyze_entry_conditions(df_analyzed)
        
        # Suggest optimizations
        self.suggest_optimizations(conditions, df_analyzed)
        
        # Create visualizations
        self.create_visualization(df_analyzed, total_entries)
        
        print(f"\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        
        entry_rate = total_entries.sum() / len(total_entries) * 100
        if entry_rate < 1:
            print(f"❌ ISSUE IDENTIFIED: Very low entry rate ({entry_rate:.2f}%)")
            print("   The strategy parameters are too restrictive for current market conditions.")
            print("   Follow the optimization recommendations above.")
        elif entry_rate < 5:
            print(f"⚠️  LOW ENTRY RATE: {entry_rate:.2f}% - strategy may be too selective")
        else:
            print(f"✅ ENTRY RATE OK: {entry_rate:.2f}%")
        
        return df_analyzed, total_entries

if __name__ == "__main__":
    diagnostic = StrategyDiagnostic()
    df_analyzed, total_entries = diagnostic.run_full_analysis()
