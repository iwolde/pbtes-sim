"""
convergence.py

Convergence diagnostics and anomaly detection tools for post-processing simulation results.
"""

import os
import pandas as pd
import numpy as np
from pbtes.analysis.results_reader import load_results

def analyze_convergence(filepath: str) -> dict:
    """
    Analyzes the convergence statistics of a simulation run.
    
    Parameters
    ----------
    filepath : str
        Path to the results CSV.
        
    Returns
    -------
    stats : dict
        A dictionary containing overall and mode-specific convergence statistics.
    """
    df, meta = load_results(filepath)
    
    if 'iter_status' not in df.columns:
        raise KeyError("The results file does not contain 'iter_status' column.")
        
    # Overall convergence
    total_steps = len(df)
    converged_steps = (df['iter_status'] == 'converged').sum()
    overall_rate = (converged_steps / total_steps * 100) if total_steps > 0 else 100.0
    
    # Mode-by-mode analysis
    mode_stats = {}
    if 'TESmode' in df.columns:
        modes = sorted(df['TESmode'].dropna().unique())
        for mode in modes:
            m_df = df[df['TESmode'] == mode]
            m_total = len(m_df)
            m_conv = (m_df['iter_status'] == 'converged').sum()
            m_rate = (m_conv / m_total * 100) if m_total > 0 else 100.0
            mode_stats[str(mode)] = {
                'total_steps': int(m_total),
                'converged_steps': int(m_conv),
                'convergence_rate': float(m_rate)
            }
            
    stats = {
        'filepath': filepath,
        'meta': meta,
        'total_steps': int(total_steps),
        'converged_steps': int(converged_steps),
        'overall_rate': float(overall_rate),
        'mode_stats': mode_stats
    }
    
    return stats

def print_convergence_report(stats: dict) -> None:
    """
    Prints a formatted convergence report to stdout.
    """
    print("\n" + "="*80)
    print(f" CONVERGENCE DIAGNOSTIC REPORT")
    print(f" File: {os.path.basename(stats['filepath'])}")
    print("="*80)
    print(f"Overall Timesteps:  {stats['total_steps']}")
    print(f"Converged Steps:    {stats['converged_steps']}")
    print(f"Overall Success %:  {stats['overall_rate']:.3f}%")
    print("-"*80)
    print(f"{'Mode':<8} | {'Total Steps':<12} | {'Converged Steps':<16} | {'Success Rate':<15}")
    print("-"*80)
    for mode, m_stats in stats['mode_stats'].items():
        print(f"{mode:<8} | {m_stats['total_steps']:<12} | {m_stats['converged_steps']:<16} | {m_stats['convergence_rate']:13.2f}%")
    print("="*80 + "\n")

def detect_anomalies(filepath: str) -> pd.DataFrame:
    """
    Identifies and returns all non-converged timesteps (anomalies) with physical context.
    
    Parameters
    ----------
    filepath : str
        Path to the results CSV.
        
    Returns
    -------
    anomalies : pd.DataFrame
        Sub-dataframe containing non-converged timesteps and relevant context columns.
    """
    df, _ = load_results(filepath)
    if 'iter_status' not in df.columns:
        return pd.DataFrame()
        
    anomalies = df[df['iter_status'] != 'converged'].copy()
    
    context_cols = [
        'time', 'E', 'Tamb', 'TESmode', 'TES_layout',
        'T_ptc_out', 'T_tes_top', 'T_tes_bottom', 'tes_soc_kWh'
    ]
    # Filter only existing columns
    existing_cols = [c for c in context_cols if c in anomalies.columns]
    
    return anomalies[existing_cols]

def get_transition_matrix(filepath: str) -> pd.DataFrame:
    """
    Computes a transition matrix of mode changes to identify unstable switching behaviors.
    
    Parameters
    ----------
    filepath : str
        Path to the results CSV.
        
    Returns
    -------
    matrix : pd.DataFrame
        A transition matrix showing counts of mode changes from row (t-1) to column (t).
    """
    df, _ = load_results(filepath)
    if 'TESmode' not in df.columns or len(df) < 2:
        return pd.DataFrame()
        
    modes = df['TESmode'].astype(str).tolist()
    
    # Create shift lists
    from_modes = modes[:-1]
    to_modes = modes[1:]
    
    # Compute cross tabulation
    transition_df = pd.crosstab(
        pd.Series(from_modes, name='From Mode (t-1)'),
        pd.Series(to_modes, name='To Mode (t)'),
        dropna=False
    )
    
    return transition_df
