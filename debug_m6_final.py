"""
MODE 6 — Isolated Convergence Test
Parallel · indirect · Two independent cycles

Tests:
  1. Design convergence (E=1000, T_bot=400)
  2. Offdesign convergence (E=1000→600, T_bot=350→500)
  3. Each test: 3 attempts via attempt_to_solve
"""
import os, shutil, numpy as np, time
from coreV5 import SolarThermalSystem, Solver

# Clean
for f in ['base_design_1','base_design_6','mode1_kA.txt']:
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
print('  MODE 6 CONVERGENCE AUDIT')
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

# ============================================================
# 2. OFFDESIGN SWEEP
# ============================================================
print('\n--- 2. OFFDESIGN SWEEP ---')
print(f'  {"E":>5s} {"T_bot":>6s} {"status":>7s} {"t(ms)":>7s} {"att":>4s}  {"T02":>6s} {"T14":>6s} {"Q_PTC(MW)":>10s}')
print(f'  {"-"*5} {"-"*6} {"-"*7} {"-"*7} {"-"*4}  {"-"*6} {"-"*6} {"-"*10}')

solver.current_irr = 0
failures = []

for E in [1000, 800, 600]:
    for T_bot in [350, 400, 450, 500]:
        sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
            HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
        sys.tes.profile = np.ones(20) * T_bot
        sys.set_operation_mode(TESmode='6', current_irr=E, mode='offdesign',
            profile=sys.tes.profile, prev_TES_lay='Charge')
        sys.conn_13.set_attr(T=T_bot)
        
        t0 = time.time()
        ok, n_att, err = solver.attempt_to_solve(sys, 'offdesign', 'base_design', '6', tries=3)
        dt_ms = (time.time() - t0) * 1000
        
        if ok and sys.network.converged:
            # Check if we're truly in Mode 6 (conn_02 exists)
            if hasattr(sys, 'conn_02'):
                t02 = sys.conn_02.T.val
                t14 = sys.conn_14.T.val
                q_ptc = sys.ptc_field.Q.val / 1e6
                print(f'  {E:5d} {T_bot:6d} {"PASS":>7s} {dt_ms:7.0f} {len(n_att):4d}  {t02:6.0f} {t14:6.0f} {q_ptc:10.3f}')
            else:
                print(f'  {E:5d} {T_bot:6d} {"FALLBK":>7s} {dt_ms:7.0f} {len(n_att):4d}  {"-":>6s} {"-":>6s} {"-":>10s}  (Mode 4)')
                failures.append((E, T_bot, 'fell to Mode 4'))
        else:
            print(f'  {E:5d} {T_bot:6d} {"FAIL":>7s} {dt_ms:7.0f} {len(n_att):4d}  {"-":>6s} {"-":>6s} {"-":>10s}')
            failures.append((E, T_bot, str(err)[:60] if err else 'unknown'))

# ============================================================
# 3. SUMMARY
# ============================================================
N = 3 * 4
conv = N - len(failures)
print(f'\n--- 3. SUMMARY ---')
print(f'  Total tests: {N}')
print(f'  Converged (M6): {conv}')
print(f'  Failed/Fallback: {len(failures)}')
if failures:
    for E, T_bot, err in failures:
        print(f'    E={E}, T_bot={T_bot}: {err}')
