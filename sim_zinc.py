"""7-day simulation with ZincPool dynamic process model."""
from coreV5 import Solver
import os, shutil, numpy as np, time

for f in ['base_design_1','base_design_2','base_design_3','base_design_4',
           'base_design_5','base_design_6','mode1_kA.txt']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

tes_p = {
    'Initial temperature': 550, 'Tank lenght': 10, 'Tank diameter': 4,
    'Particle diameter': 0.05, 'Void fraction': 0.4,
    'Solid density': 3500, 'Solid specific heat': 968, 'Solid conductivity': 1.5,
    'Wall thinckness': 0.05, 'Tank conductivity': 15,
    'Insulation thickness': 0.5, 'Insulation conductivity': 0.035,
    'HTF': 'INCOMP::NaK'
}
comp_p = {
    'ptc_A': 2500, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -450000
}
conn_p = {
    '5_T': 520, '6_T': 480, '6_p': 50,
    '6_f': {'INCOMP::NaK': 1}, '13_p': 5,
    '13_f': {'INCOMP::NaK': 1}, '15_p': 5, '15_f': {'INCOMP::NaK': 1}
}
zinc_p = {
    'mass': 150e3,               # 150 tons zinc
    'temp_initial': 450,         # start at 450°C
    'cp_zinc': 512,              # J/kgK
    'UA_loss': 500,              # W/K heat loss
    'target_temp': 450,          # target operating temp
    'ttd_hx': 20,                # HX approach ΔT
    'op_start_hour': 8,          # production 8am-8pm
    'op_end_hour': 20,
    'op_days_per_week': 5,       # Mon-Fri
    'mass_steel_per_hour': 5000, # 5 tons/hr steel
    'cp_steel': 460,
    'T_steel_inlet': 25
}

solver = Solver(
    tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect',
    charge_margin=1.5, zinc_pool_params=zinc_p
)

print('=== Initializing design modes (zinc pool) ===')
t0 = time.time()
solver.initialize_modes()
solver.tes_params['Initial temperature'] = 550
print(f'Design initialization: {time.time()-t0:.0f}s')

DAYS = 365
print(f'\n=== Running {DAYS}-day simulation (zinc pool, T_init=550C) ===')
t0 = time.time()
solver.run_quasi_steady_simulation(days_to_simulate=DAYS, E_col='dni', Tamb_col='temp')
elapsed = time.time() - t0
print(f'Simulation completed in {elapsed:.0f}s')

results = solver.results
if not results:
    print('No results!')
    exit()

N = len(results)
modes = [r.get('TESmode', '?') for r in results]
counts = {m: modes.count(m) for m in sorted(set(modes))}

print(f'\n--- Mode Distribution ({DAYS}d) ---')
for m in sorted(counts, key=lambda x: str(x)):
    print(f'  Mode {m}: {counts[m]}h ({100*counts[m]/N:.1f}%)')

# Zinc pool evolution
if solver.zinc_pool:
    zt = [r.get('zinc_pool_temp', None) for r in results]
    zt_valid = [t for t in zt if t is not None]
    if zt_valid:
        print(f'\nZinc pool: initial={zinc_p["temp_initial"]}C, '
              f'final={zt_valid[-1]:.0f}C, min={min(zt_valid):.0f}C, max={max(zt_valid):.0f}C')

# TES
if solver.TES_profiles and solver.TES_profiles[0] is not None:
    p = solver.TES_profiles[0]
    print(f'TES Day 1: T_min={min(p):.0f}C T_max={max(p):.0f}C T_mean={np.mean(p):.0f}C')

# Energy
solar_to_proc = sum(r.get('solar_to_proc_kJ', 0) for r in results) / 1e6
tes_to_proc = sum(r.get('tes_to_proc_kJ', 0) for r in results) / 1e6
to_tes = sum(r.get('to_tes_kJ', 0) for r in results) / 1e6
aux_to_proc = sum(r.get('aux_to_proc_kJ', 0) for r in results) / 1e6
ptc_total = sum(r.get('ptc_total_kJ', 0) for r in results) / 1e6
q_proc = sum(r.get('process_hx_Q_kW', 0) for r in results) * 3.6 / 1e6  # kW*h to GJ

total = solar_to_proc + tes_to_proc + aux_to_proc
sf = (solar_to_proc + tes_to_proc) / max(total, 1) * 100

print(f'\nEnergy (GJ): solar_to_proc={solar_to_proc:.0f} tes_to_proc={tes_to_proc:.0f} '
      f'to_tes={to_tes:.0f} aux={aux_to_proc:.0f} ptc={ptc_total:.0f} Q_proc={q_proc:.0f}')
print(f'SOLAR FRACTION: {sf:.1f}%')
converged = sum(1 for r in results if r.get('network_converged', False))
print(f'Converged: {converged}/{N}')

# Monthly breakdown
irr = [r.get('E', 0) for r in results]
from datetime import datetime
times = [r.get('time') for r in results]
if times and isinstance(times[0], datetime):
    print(f'\n--- Monthly Breakdown ---')
    print(f' Mo |  SF% | DNI_avg | DNI_max | Ttop_avg | Ttop_max | Tbot_avg | Tbot_min | Qchg_GJ | Qdch_GJ | Qaux_GJ | Top modes')
    print(f'----|------|---------|---------|----------|----------|----------|----------|---------|---------|---------|----------')
    for month in range(1, 13):
        idx = [i for i, t in enumerate(times) if t.month == month]
        if not idx: continue
        mon_irr = [irr[i] for i in idx]
        s  = sum(results[i].get('solar_to_proc_kJ',0) for i in idx) / 1e6
        t  = sum(results[i].get('tes_to_proc_kJ',0) for i in idx) / 1e6
        a  = sum(results[i].get('aux_to_proc_kJ',0) for i in idx) / 1e6
        qc = sum(results[i].get('to_tes_kJ',0) for i in idx) / 1e6
        qd = sum(results[i].get('tes_to_proc_kJ',0) for i in idx) / 1e6
        sf = (s + t) / max(s + t + a, 1) * 100
        tops = [results[i].get('T_tes_top', np.nan) for i in idx]
        bots = [results[i].get('T_tes_bottom', np.nan) for i in idx]
        tops_v = [v for v in tops if not np.isnan(v)]
        bots_v = [v for v in bots if not np.isnan(v)]
        mcounts = {}
        for i in idx:
            m = str(results[i].get('TESmode', '?'))
            mcounts[m] = mcounts.get(m, 0) + 1
        top3 = sorted(mcounts.items(), key=lambda x: -x[1])[:3]
        mode_str = ' '.join(f'{md}:{hr}h' for md, hr in top3)
        print(f' {month:2d} | {sf:4.1f} | {np.mean(mon_irr):7.0f} | {np.max(mon_irr):7.0f} | '
              f'{np.mean(tops_v):8.0f} | {np.max(tops_v) if tops_v else 0:8.0f} | '
              f'{np.mean(bots_v):8.0f} | {np.min(bots_v) if bots_v else 0:8.0f} | '
              f'{qc:7.0f} | {qd:7.0f} | {a:7.0f} | {mode_str}')
