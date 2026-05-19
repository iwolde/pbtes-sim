"""Yearly simulation - improved design (thick insulation, D=4m)"""
from coreV5 import Solver
import os, shutil, numpy as np
import time

for f in ['base_design_1','base_design_2','base_design_3','base_design_4',
           'base_design_5','base_design_6','mode1_kA.txt']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f):
                os.remove(f)
            else:
                shutil.rmtree(f, ignore_errors=True)
        except:
            pass

tes_p = {
    'Initial temperature': 550,
    'Tank lenght': 10,
    'Tank diameter': 6,             # D=6m for 2.25x more thermal mass
    'Particle diameter': 0.05,
    'Void fraction': 0.4,
    'Solid density': 3500,
    'Solid specific heat': 968,
    'Solid conductivity': 1.5,
    'Wall thinckness': 0.05,
    'Tank conductivity': 15,
    'Insulation thickness': 0.5,
    'Insulation conductivity': 0.035,
    'HTF': 'INCOMP::NaK'
}
comp_p = {
    'ptc_A': 2500, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -450000
}
conn_p = {
    '5_T': 520, '6_T': 480, '6_p': 50,
    '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'INCOMP::NaK': 1},
    '15_p': 5, '15_f': {'INCOMP::NaK': 1}
}
comp_p = {
    'ptc_A': 2500, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -1e6
}
conn_p = {
    '5_T': 520, '6_T': 450, '6_p': 50,
    '6_f': {'INCOMP::NaK': 1}, '13_p': 5,
    '13_f': {'INCOMP::NaK': 1}, '15_p': 5,
    '15_f': {'INCOMP::NaK': 1}
}

solver = Solver(
    tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect',
    charge_margin=1.5
)

print('=== Initializing design modes (A=2500 m2, D=4m, ins=0.5m) ===')
t0 = time.time()
solver.initialize_modes()
solver.tes_params['Initial temperature'] = 550
print(f'Design initialization: {time.time()-t0:.0f}s')

DAYS = 365
print(f'\n=== Running {DAYS}-day simulation (T_init=550C) ===')
t0 = time.time()
solver.run_quasi_steady_simulation(days_to_simulate=DAYS, E_col='dni', Tamb_col='temp')
elapsed = time.time() - t0
print(f'Simulation completed in {elapsed:.0f}s ({elapsed/max(DAYS,1):.1f}s/day)')

results = solver.results
N = len(results)
if not N:
    print('No results!')
    exit()

modes = [r.get('TESmode', '?') for r in results]
counts = {m: modes.count(m) for m in sorted(set(modes))}

print(f'\n--- Mode Distribution ({DAYS}d) ---')
for m in sorted(counts, key=lambda x: str(x)):
    pct = 100 * counts[m] / N
    print(f'  Mode {m}: {counts[m]}h ({pct:.1f}%)')

irr = [r.get('E', 0) for r in results]
print(f'DNI: mean={np.mean(irr):.0f} max={np.max(irr):.0f} W/m2')

# TES evolution
if solver.TES_profiles:
    print(f'\n--- TES Temperature (daily) ---')
    for i in range(0, len(solver.TES_profiles), 24):
        p = solver.TES_profiles[i]
        if p is not None and len(p) > 0:
            day = i // 24 + 1
            print(f'  Day {day}: T_min={min(p):.0f}C T_max={max(p):.0f}C T_mean={np.mean(p):.0f}C')

# Energy summary
solar_to_proc = sum(r.get('solar_to_proc_kJ', 0) for r in results) / 1e6
tes_to_proc = sum(r.get('tes_to_proc_kJ', 0) for r in results) / 1e6
to_tes = sum(r.get('to_tes_kJ', 0) for r in results) / 1e6
aux_to_proc = sum(r.get('aux_to_proc_kJ', 0) for r in results) / 1e6
ptc_total = sum(r.get('ptc_total_kJ', 0) for r in results) / 1e6

total = solar_to_proc + tes_to_proc + aux_to_proc
sf = (solar_to_proc + tes_to_proc) / max(total, 1) * 100

print(f'\nEnergy (GJ): solar_to_proc={solar_to_proc:.0f} tes_to_proc={tes_to_proc:.0f} '
      f'to_tes={to_tes:.0f} aux={aux_to_proc:.0f} ptc={ptc_total:.0f}')
print(f'SOLAR FRACTION: {sf:.1f}%')

# Convergence
converged = sum(1 for r in results if r.get('network_converged', False))
print(f'Converged: {converged}/{N} ({100*converged/max(N,1):.1f}%)')
if converged < N:
    for m in sorted(counts):
        fbs = sum(1 for r in results if r.get('TESmode') == m and not r.get('network_converged', True))
        if fbs > 0:
            print(f'  Mode {m} fallbacks: {fbs}/{counts[m]}')
