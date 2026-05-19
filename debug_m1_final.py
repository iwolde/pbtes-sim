"""
MODE 1 — Isolated Convergence Test
Parallel · indirect · PTC splits to Process + TES

Tests:
  1. Design convergence (E=1000, T_bot=400)
  2. Offdesign convergence (E=1000→400, T_bot=350→500)
  3. Each test: 3 attempts via attempt_to_solve
"""
import os, shutil, numpy as np, time
from coreV5 import SolarThermalSystem, Solver

# Clean
for f in ['base_design_1','base_design_4','mode1_kA.txt']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

tes_p = {
    'Initial temperature': 400, 'Tank lenght': 10, 'Tank diameter': 4,
    'Particle diameter': 0.05, 'Void fraction': 0.4, 'Solid density': 2500,
    'Solid specific heat': 1000, 'Solid conductivity': 1.5,
    'Wall thinckness': 0.05, 'Tank conductivity': 15,
    'Insulation thickness': 0.5, 'Insulation conductivity': 0.035,
    'HTF': 'INCOMP::NaK'
}
comp_p = {
    'ptc_A': 2500, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -1e6
}
conn_p = {
    '5_T': 520, '6_T': 480, '6_p': 50, '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'INCOMP::NaK': 1}, '15_p': 5, '15_f': {'INCOMP::NaK': 1}
}

print('='*60)
print('  MODE 1 CONVERGENCE AUDIT')
print('='*60)

# ============================================================
# 1. DESIGN
# ============================================================
print('\n--- 1. DESIGN (E=1000, T_bot=400) ---')
solver = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
t0 = time.time()
solver.initialize_modes()
dt = time.time() - t0
print(f'  Initialize: {dt:.1f}s')
print(f'  Mode 1 kA = {solver.charge_hx_kA:.0f} W/K')
print(f'  Design PTC A = {solver.solar_system.ptc_field.A.val:.0f} m2')

# ============================================================
# 2. OFFDESIGN — sweep E (1000→400) × T_bot (350→500)
# ============================================================
print('\n--- 2. OFFDESIGN SWEEP ---')
print(f'  {"E":>5s} {"T_bot":>6s} {"status":>7s} {"t(ms)":>7s} {"att":>4s}  {"T02":>6s} {"T14":>6s} {"Q_PTC(MW)":>10s} {"err"}')
print(f'  {"-"*5} {"-"*6} {"-"*7} {"-"*7} {"-"*4}  {"-"*6} {"-"*6} {"-"*10} {"-"*20}')

solver.current_irr = 0
failures = []

for E in [1000, 900, 800, 700, 600, 500, 400]:
    for T_bot in [350, 400, 450, 500]:
        sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
            HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
        sys.tes.profile = np.ones(20) * T_bot
        sys.set_operation_mode(TESmode='1', current_irr=E, mode='offdesign',
            profile=sys.tes.profile, prev_TES_lay='Charge')
        sys.conn_13.set_attr(T=T_bot)
        
        t0 = time.time()
        ok, n_att, err = solver.attempt_to_solve(sys, 'offdesign', 'base_design', '1', tries=3)
        dt_ms = (time.time() - t0) * 1000
        
        if ok and sys.network.converged:
            t02 = sys.conn_02.T.val
            t14 = sys.conn_14.T.val
            q_ptc = sys.ptc_field.Q.val / 1e6
            n_tries = len(n_att) if isinstance(n_att, list) else n_att
            print(f'  {E:5d} {T_bot:6d} {"PASS":>7s} {dt_ms:7.0f} {n_tries:4d}  {t02:6.0f} {t14:6.0f} {q_ptc:10.3f}')
        else:
            err_msg = str(err)[:40] if err else 'unknown'
            print(f'  {E:5d} {T_bot:6d} {"FAIL":>7s} {dt_ms:7.0f} {"-":>4s}  {"-":>6s} {"-":>6s} {"-":>10s}  {err_msg}')
            failures.append((E, T_bot, err_msg))

# ============================================================
# 3. SUMMARY
# ============================================================
N = 7 * 4  # 7 E values × 4 T_bot values
print(f'\n--- 3. SUMMARY ---')
print(f'  Total tests: {N}')
print(f'  Passed: {N - len(failures)}')
print(f'  Failed: {len(failures)}')
if failures:
    print(f'  Failures:')
    for E, T_bot, err in failures:
        print(f'    E={E}, T_bot={T_bot}: {err}')
