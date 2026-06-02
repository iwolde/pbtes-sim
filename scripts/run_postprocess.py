"""
run_postprocess.py

Post-processing pipeline script.
Reads generated simulation results (CSVs), calculates pressure drops and
pump power (since they are omitted from the inline TESPy simulation),
and outputs processed CSVs.

Usage:
    python scripts/run_postprocess.py results/baseline_run.csv
    python scripts/run_postprocess.py results/*.csv
"""

import sys
import os
import glob
import json

# Ensure parent directory is in path so 'pbtes' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbtes.analysis.results_reader import load_results
from pbtes.analysis.postprocess import calculate_system_pump_power

def process_file(filepath: str):
    print(f"Processing: {filepath}")
    try:
        # Load the dataframe and the metadata
        df, meta = load_results(filepath)
        
        # Calculate pump power and append to dataframe
        df = calculate_system_pump_power(df, meta)
        
        # Calculate summary metrics for feedback
        total_pump_MWh = df['W_pump_kW'].sum() / 1000.0  # 1-hour steps
        
        # Updated Solar Fraction (Thermal)
        q_solar = df['solar_to_proc_kJ'].sum() + df['tes_to_proc_kJ'].sum()
        q_aux_tes = df.get('aux_tes_energy_kJ', 0.0).sum() if 'aux_tes_energy_kJ' in df.columns else 0.0
        q_total = q_solar + df['aux_to_proc_kJ'].sum() + q_aux_tes
        sf_thermal = (q_solar / q_total) * 100 if q_total > 0 else 0
        
        print(f"  -> Total pump energy: {total_pump_MWh:.3f} MWh/year")
        if q_aux_tes > 0:
            print(f"  -> Total tank aux:    {q_aux_tes / 3.6e9:.3f} MWh")
        print(f"  -> Thermal SF:        {sf_thermal:.1f}%")
        
        # Create output filename
        base, ext = os.path.splitext(filepath)
        out_filepath = f"{base}_processed{ext}"
        
        # Write back to CSV while preserving the __meta__ header
        with open(out_filepath, 'w', encoding='utf-8') as f:
            f.write(f"__meta__,{json.dumps(meta)}\n")
            
        df.to_csv(out_filepath, mode='a', index=False)
        print(f"  -> Saved to {out_filepath}")
        
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

def main():
    if len(sys.args) < 2:
        print("Usage: python run_postprocess.py <results_file.csv> [<more_files.csv> ...]")
        sys.exit(1)
        
    file_patterns = sys.args[1:]
    files_to_process = []
    
    for pattern in file_patterns:
        matches = glob.glob(pattern)
        if not matches:
            # Maybe the user passed the literal path without expanding
            if os.path.exists(pattern):
                files_to_process.append(pattern)
        else:
            files_to_process.extend(matches)
            
    # Remove duplicates
    files_to_process = list(set(files_to_process))
    
    if not files_to_process:
        print("No files found matching the provided arguments.")
        sys.exit(1)
        
    for filepath in files_to_process:
        if filepath.endswith('_processed.csv'):
            print(f"Skipping already processed file: {filepath}")
            continue
        process_file(filepath)

if __name__ == '__main__':
    # Fix for sys.args typo in standard python (sys.argv)
    import sys as _sys
    sys.args = _sys.argv
    main()
