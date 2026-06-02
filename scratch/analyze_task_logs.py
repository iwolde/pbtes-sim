import os
import sys

def analyze_log(log_path, label):
    if not os.path.exists(log_path):
        print(f"Log not found: {log_path}")
        return
        
    print(f"\n==================================================")
    print(f"LOG ANALYSIS FOR {label}: {log_path}")
    print(f"==================================================")
    
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    lines = content.split('\n')
    print(f"Total log lines: {len(lines)}")
    
    # Count specific phrases
    retries = content.count("Attempt 1 failed to converge. Retrying...")
    failed_attempts = content.count("failed to converge. Retrying...")
    fallbacks = content.count("Solver failed after 5 attempts")
    warnings = content.count("[WARNING]")
    mode_changes = content.count("passing to") + content.count("reverting to")
    
    print(f"  Attempt 1 failed (initial retries): {retries}")
    print(f"  Total randomized retries:           {failed_attempts}")
    print(f"  Mode solver failures (fallbacks):   {fallbacks}")
    print(f"  Warnings printed:                   {warnings}")
    print(f"  Solver mode fallbacks:              {mode_changes}")
    
    # Show unique warnings or solver failure lines
    solver_fails = [line for line in lines if "Solver failed after" in line]
    print(f"\nMode Solver Failures ({len(solver_fails)}):")
    for line in solver_fails[:10]:
        print(f"  {line}")
    if len(solver_fails) > 10:
        print("  ...")
        
    warnings_lines = [line for line in lines if "[WARNING]" in line]
    print(f"\nWarnings printed ({len(warnings_lines)}):")
    for line in set(warnings_lines[:15]):
        print(f"  {line}")
    if len(warnings_lines) > 15:
        print("  ...")

# We know the appDataDir and task numbers.
# AppDataDir is C:\Users\iwold\.gemini\antigravity
log_pi = r"C:\Users\iwold\.gemini\antigravity\brain\aabcf487-ccd4-4f99-8b8f-12e52c016a76\.system_generated\tasks\task-27.log"
log_sd = r"C:\Users\iwold\.gemini\antigravity\brain\aabcf487-ccd4-4f99-8b8f-12e52c016a76\.system_generated\tasks\task-44.log"

analyze_log(log_pi, "Parallel/Indirect (PI)")
analyze_log(log_sd, "Series/Direct (SD)")
