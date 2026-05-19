"""Monthly simulation - tank pre-charged at 500C"""
from coreV5 import Solver
import os, shutil, numpy as np

for f in ['base_design_1','base_design_2','base_design_3','base_design_4','base_design_5','base_design_6','mode1_kA.txt']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

tes_p = {'Initial temperature': 500, 'Tank lenght': 10, 'Tank diameter': 3,
    'Particle diameter': 0.05, 'Void fraction': 0.4, 'Solid density': 2500,
    'Solid specific heat': 1000, 'Solid conductivity': 1.5, 'Wall thinckness': 0.05,
    'Tank conductivity': 15, 'Insulation thickness': 0.2, 'Insulation conductivity': 0.05,
    'HTF': 'INCOMP::NaK'}
comp_p = {'ptc_A': 2500, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -1e6}
conn_p = {'5_T': 520, '6_T': 480, '6_p': 50, '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'INCOMP::NaK': 1}, '15_p': 5, '15_f': {'INCOMP::NaK': 1}}

solver = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect', charge_margin=1.5)

print('=== Initializing design modes (A=2500) ===')
solver.initialize_modes()
solver.tes_params['Initial temperature'] = 500  # Reset after initialize_modes changes it
print()

print('=== Running 30-day simulation (tank initially at 500C) ===')
solver.run_quasi_steady_simulation(days_to_simulate=30, E_col='dni', Tamb_col='temp')

results = solver.results
if results:
    modes = [r.get('TESmode','?') for r in results]
    counts = {m: modes.count(m) for m in set(modes)}
    print(f'\n=== Mode Distribution (30 days) ===')
    for m in sorted(counts):
        print(f'  Mode {m}: {counts[m]}h ({100*counts[m]/len(modes):.0f}%)')
    
    irr = [r.get('E',0) for r in results]
    print(f'\nIrradiance: mean={np.mean(irr):.0f} max={np.max(irr):.0f} W/m2')
    
    # TES evolution
    if solver.TES_profiles:
        # Sample every 24 hours
        for i in range(0, len(solver.TES_profiles), 24):
            p = solver.TES_profiles[i]
            if p is not None and len(p) > 0:
                day = i // 24 + 1
                print(f'  Day {day}: T_min={min(p):.0f}C T_max={max(p):.0f}C')
    
    # Energy summary
    solar_to_proc = sum(r.get('solar_to_proc_kJ',0) for r in results) / 1e6  # GJ
    tes_to_proc = sum(r.get('tes_to_proc_kJ',0) for r in results) / 1e6
    to_tes = sum(r.get('to_tes_kJ',0) for r in results) / 1e6
    aux_to_proc = sum(r.get('aux_to_proc_kJ',0) for r in results) / 1e6
    ptc_total = sum(r.get('ptc_total_kJ',0) for r in results) / 1e6
    print(f'\nEnergy (GJ): solar_to_proc={solar_to_proc:.1f} tes_to_proc={tes_to_proc:.1f} to_tes={to_tes:.1f} aux={aux_to_proc:.1f} ptc_total={ptc_total:.1f}')
else:
    print('No results!')
