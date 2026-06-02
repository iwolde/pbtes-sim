import os
import sys
import pandas as pd
import numpy as np

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pbtes.analysis.results_reader import load_results

def analyze_retries(filepath):
    print(f"\n==================================================")
    print(f"RETRIAL & FALLBACK ANALYSIS FOR: {filepath}")
    print(f"==================================================")
    
    df, meta = load_results(filepath)
    total_steps = len(df)
    
    # Check retries
    retried_steps = df[df['attempt_count'] > 1]
    print(f"Total steps: {total_steps}")
    print(f"Steps requiring retries/fallbacks: {len(retried_steps)} ({len(retried_steps)/total_steps*100:.2f}%)")
    
    # Max attempts
    print(f"Max attempts in a single step: {df['attempt_count'].max()}")
    
    # Distribution of attempt counts
    print("\nAttempt counts distribution:")
    attempt_dist = df['attempt_count'].value_counts().sort_index()
    for attempts, count in attempt_dist.items():
        print(f"  {attempts} attempt(s): {count} ({count/total_steps*100:.2f}%)")
        
    # Analyze fallbacks (where attempted_modes has more than one unique mode, or where the final mode differs from the initial mode)
    fallback_count = 0
    for idx, row in df.iterrows():
        try:
            # attempted_modes is loaded as a list by results_reader
            modes = row['attempted_modes']
            if isinstance(modes, list) and len(set(modes)) > 1:
                fallback_count += 1
        except Exception:
            pass
            
    print(f"\nSteps that had mode fallbacks: {fallback_count} ({fallback_count/total_steps*100:.2f}%)")

print("Analyzing PI baseline retries...")
analyze_retries("results/PI_90d_Parallel_indirect_NaK_D7.0_H5.0_A1000_90d_20260602.csv")

print("\nAnalyzing SD baseline retries...")
analyze_retries("results/SD_90d_Series_direct_NaK_D7.0_H5.0_A1000_90d_20260602.csv")
