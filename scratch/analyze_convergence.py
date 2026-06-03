import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbtes.analysis.convergence import (
    analyze_convergence,
    print_convergence_report,
    detect_anomalies,
    get_transition_matrix
)

def main():
    if len(sys.argv) < 2:
        print("Usage: python scratch/analyze_convergence.py <results_file.csv>")
        sys.exit(1)
        
    filepath = sys.argv[1]
    
    # 1. Print standard convergence stats
    stats = analyze_convergence(filepath)
    print_convergence_report(stats)
    
    # 2. Anomaly detection
    anomalies = detect_anomalies(filepath)
    if not anomalies.empty:
        print(f"\nDetected {len(anomalies)} Non-Converged Timesteps:")
        print(anomalies.to_string(index=False))
    else:
        print("\nNo non-converged timesteps detected! 100% convergence achieved.")
        
    # 3. Transition matrix
    trans_matrix = get_transition_matrix(filepath)
    if not trans_matrix.empty:
        print("\nMode Transition Matrix (Counts of transitions from Row to Column):")
        print(trans_matrix.to_string())

if __name__ == '__main__':
    main()
