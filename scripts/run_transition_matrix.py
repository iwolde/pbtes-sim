import os
import sys
import numpy as np

# Add parent directory to path to import coreV5
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from coreV5 import SolarThermalSystem, Solver

def generate_report():
    tes_params = {
        'Initial temperature': 500,
        'Tank length': 10,
        'Tank diameter': 3,
        'Particle diameter': 0.05,
        'Void fraction': 0.4,
        'Solid density': 2500,
        'Solid specific heat': 1000,
        'Solid conductivity': 1.5,
        'Wall thickness': 0.05,
        'Tank conductivity': 15,
        'Insulation thickness': 0.2,
        'Insulation conductivity': 0.05,
        'HTF': 'INCOMP::NaK'
    }
    
    component_params = {
        'ptc_A': 10000,
        'ptc_aoi': 0.0,
        'ptc_doc': 1.0,
        'ptc_tamb': 20.0,
        'eta_opt': 0.75,
        'ptc_c_1': 0.0,
        'ptc_c_2': 0.0,
        'ptc_E': 1000.0,
        'ptc_iam_1': 0.0,
        'ptc_iam_2': 0.0,
        'PR_Q': -1e6
    }
    
    conexion_params = {
        '5_T': 520,
        '6_T': 300,
        '6_p': 5,
        '6_f': {'Water': 1}
    }
    
    system_params = {
        'tes_params': tes_params,
        'component_params': component_params,
        'conexion_params': conexion_params,
        'HTF': 'INCOMP::NaK',
        'topology': 'Parallel'
    }

    modes = [1, 2, 3, 4, 6]
    report_lines = []
    report_lines.append("# Transition Matrix Report")
    report_lines.append("")
    report_lines.append("This report outlines the result of transitioning from any mode to any other mode.")
    report_lines.append("")
    
    exceptions = []

    profile = np.ones(20) * 500

    for from_mode in modes:
        for to_mode in modes:
            system = SolarThermalSystem(**system_params)
            solver = Solver(**system_params)
            
            irr_from = 1000 if from_mode in [1, 2, 6] else 0
            solver.current_irr = irr_from
            
            try:
                system.create_network(mode=from_mode)
                if from_mode in [1, 6]:
                    system.tes.set_state('charge')
                elif from_mode == 3:
                    system.tes.set_state('discharge')
                
                # Attempt to solve from_mode, but if it fails it's fine, we are testing the transition
                try:
                    solver.attempt_to_solve(system, 'design', 'base_design', str(from_mode), tries=1)
                except Exception:
                    pass
                
                irr_to = 1000 if to_mode in [1, 2, 6] else 0
                solver.current_irr = irr_to
                prev_lay = 'Charge' if from_mode in [1, 6] else 'Discharge'
                
                system.set_operation_mode(TESmode=str(to_mode), current_irr=irr_to, profile=profile, prev_TES_lay=prev_lay, mode='design')
                
                ok, attempts, err = solver.attempt_to_solve(system, 'design', 'base_design', str(to_mode), tries=1)
                
                if not ok:
                    status = "Failed (but caught)"
                else:
                    if attempts[-1]['mode'] == '4' and str(to_mode) != '4':
                        status = "Fallback to Mode 4"
                    else:
                        status = "Success"
                        
                report_lines.append(f"- **{from_mode} -> {to_mode}**: {status}")
                
            except Exception as e:
                report_lines.append(f"- **{from_mode} -> {to_mode}**: Unhandled Exception")
                exceptions.append((from_mode, to_mode, str(e)))

    if exceptions:
        report_lines.append("")
        report_lines.append("## Unhandled Exceptions")
        for ex in exceptions:
            report_lines.append(f"- **{ex[0]} -> {ex[1]}**: {ex[2]}")
    else:
        report_lines.append("")
        report_lines.append("## Unhandled Exceptions")
        report_lines.append("None found.")

    report_path = "transition_report.md"
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
        
    print(f"Report generated successfully at {report_path}")

if __name__ == "__main__":
    generate_report()
