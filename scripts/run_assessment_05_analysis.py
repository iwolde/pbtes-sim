"""
Assessment 05 — Convergence & Error Analysis
Runs errors_analysis.run_all_analyses on the baseline CSV(s).
Produces statistical tables, heatmaps, and anomaly detection outputs.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from errors_analysis import run_all_analyses

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'article_results')
ANALYSIS_DIR = os.path.join(BASE_DIR, '05_analysis')

def main():
    # Analyze Parallel baseline
    parallel_csv = os.path.join(BASE_DIR, '01_baseline', 'baseline_parallel.csv')
    if os.path.exists(parallel_csv):
        out = os.path.join(ANALYSIS_DIR, 'baseline_parallel')
        os.makedirs(out, exist_ok=True)
        print(f'Analyzing {parallel_csv} → {out}')
        run_all_analyses(parallel_csv, out)
    else:
        print(f'⚠ {parallel_csv} not found — run Assessment 01 first.')

    # Analyze Series baseline (if it exists)
    series_csv = os.path.join(BASE_DIR, '01_baseline', 'baseline_series.csv')
    if os.path.exists(series_csv):
        out = os.path.join(ANALYSIS_DIR, 'baseline_series')
        os.makedirs(out, exist_ok=True)
        print(f'Analyzing {series_csv} → {out}')
        run_all_analyses(series_csv, out)

    print('\n✅ Assessment 05 complete.')


if __name__ == '__main__':
    main()
