"""
run_exergoeconomics.py

Runner script for the exergoeconomic assessment.
Reads generated simulation results (CSVs) and evaluates exergoeconomic performance.

Usage:
    python scripts/run_exergoeconomics.py results/baseline_run.csv
"""

import sys
import os
import glob
import json

# Ensure parent directory is in path so 'pbtes' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbtes.analysis.results_reader import load_results
from pbtes.analysis.exergoeconomics import ExergoeconomicAssessment

def process_file(filepath: str):
    print(f"Running Exergoeconomic Assessment: {filepath}")
    try:
        # Load the dataframe and the metadata
        df, meta = load_results(filepath)
        
        # Run Exergoeconomic Assessment
        exergo = ExergoeconomicAssessment(df, meta)
        results = exergo.run_exergoeconomic_assessment()
        
        # Add exergoeconomic results to meta to save it
        meta['exergoeconomics'] = results
        
        # Output summary
        print(f"  -> Plant Exergy Efficiency: {results['eta_exergy']:.2f}%")
        print(f"  -> Total Exergy Destruction: {results['Ex_destruction_MWh']:.2f} MWh")
        print(f"  -> Specific Cost of Product Exergy: {results['c_p_usd_per_MWh_ex']:.2f} USD/MWh_ex")
        print(f"  -> Exergoeconomic Factor (f): {results['exergoeconomic_f_factor']:.3f}")
        
        # Create output filename
        base, ext = os.path.splitext(filepath)
        out_filepath = f"{base}_exergo{ext}"
        
        # Write back to CSV while preserving the __meta__ header
        with open(out_filepath, 'w', encoding='utf-8') as f:
            f.write(f"__meta__,{json.dumps(meta)}\n")
            
        df.to_csv(out_filepath, mode='a', index=False)
        print(f"  -> Saved to {out_filepath}")
        
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

def main():
    if len(sys.args) < 2:
        print("Usage: python run_exergoeconomics.py <results_file.csv> [<more_files.csv> ...]")
        sys.exit(1)
        
    file_patterns = sys.args[1:]
    files_to_process = []
    
    for pattern in file_patterns:
        matches = glob.glob(pattern)
        if not matches:
            if os.path.exists(pattern):
                files_to_process.append(pattern)
        else:
            files_to_process.extend(matches)
            
    files_to_process = list(set(files_to_process))
    
    if not files_to_process:
        print("No files found matching the provided arguments.")
        sys.exit(1)
        
    for filepath in files_to_process:
        if filepath.endswith('_exergo.csv'):
            continue
        process_file(filepath)

if __name__ == '__main__':
    import sys as _sys
    sys.args = _sys.argv
    main()
