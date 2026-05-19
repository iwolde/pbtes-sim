"""Yearly simulation - Archive configuration (D=5, H=3, PTC A=1000, eta=0.816)."""
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
    'Initial temperature': 520,
    'Tank lenght': 3,               # archive: 3 m (shorter, wider)
    'Tank diameter': 5,             # archive: 5 m
    'Particle diameter': 0.05,
    'Void fraction': 0.4,
    'Solid density': 3500,          # archive
    'Solid specific heat': 968,     # archive
    'Solid conductivity': 1.6,      # archive
    'Wall thinckness': 0.01,        # archive: 10 mm
    'Tank conductivity': 45,        # archive
    'Insulation thickness': 0.5,
    'Insulation conductivity': 0.03, # archive
    'HTF': 'INCOMP::NaK'              # NaK for much better heat transfer
}
comp_p = {
    'ptc_A': 1000,
    'ptc_aoi': 20,
    'ptc_doc': 1,
    'ptc_tamb': 20,
    'eta_opt': 0.816,
    'ptc_c_1': 0.0622,
    'ptc_c_2': 0.00023,
    'ptc_E': 900,
    'ptc_iam_1': -1.59e-3,
    'ptc_iam_2': 9.77e-5,
    'PR_Q': -450000
}
conn_p = {
    '5_T': 520, '6_T': 480, '6_p': 50,
    '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'INCOMP::NaK': 1},  # NaK in TES
    '15_p': 5, '15_f': {'INCOMP::NaK': 1}   # NaK in TES
}
conn_p = {
    '5_T': 520, '6_T': 480, '6_p': 50,
    '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'Air': 1},       # Air TES
    '15_p': 5, '15_f': {'Air': 1}        # Air TES
}

solver = Solver(
    tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect',
    charge_margin=1.5
)

print('=== Initializing design modes (archive config) ===')
t0 = time.time()
solver.initialize_modes()
solver.tes_params['Initial temperature'] = 520
print(f'Design initialization: {time.time()-t0:.0f}s')

DAYS = 365
print(f'\n=== Running {DAYS}-day simulation (T_init=520C) ===')
t0 = time.time()
solver.run_quasi_steady_simulation(days_to_simulate=DAYS, E_col='dni', Tamb_col='temp')
elapsed = time.time() - t0
print(f'Simulation completed in {elapsed:.0f}s ({elapsed/DAYS:.1f}s/day)')

results = solver.results
if not results:
    print('No results!')
    exit()

N = len(results)
modes = [r.get('TESmode', '?') for r in results]
counts = {m: modes.count(m) for m in sorted(set(modes))}

print(f'\n{"="*60}')
print(f'  YEARLY SIMULATION RESULTS ({DAYS} days, {N} hours)')
print(f'{"="*60}')

print(f'\n--- Mode Distribution ---')
for m in sorted(counts, key=lambda x: str(x)):
    pct = 100 * counts[m] / N
    print(f'  Mode {m}: {counts[m]:5d}h ({pct:5.1f}%)')

irr = [r.get('E', 0) for r in results]
print(f'\nDNI: mean={np.mean(irr):.0f} max={np.max(irr):.0f} W/m2')

# TES evolution (weekly)
if solver.TES_profiles:
    print(f'\n--- TES Temperature (weekly) ---')
    for i in range(0, len(solver.TES_profiles), max(1, 24 * 7)):
        p = solver.TES_profiles[i]
        if p is not None and len(p) > 0:
            week = i // (24 * 7) + 1
            print(f'  Week {week:2d}: T_min={min(p):.0f}C T_max={max(p):.0f}C T_mean={np.mean(p):.0f}C')
            if week > 3: break

# Energy
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

converged = sum(1 for r in results if r.get('network_converged', False))
print(f'Converged: {converged}/{N}')
