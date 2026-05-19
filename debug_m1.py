"""Mode 1 audit: Parallel charge (PTC splits to process + TES)."""
import os, shutil, numpy as np
from coreV5 import SolarThermalSystem, Solver

for f in ['base_design_1','base_design_4','mode1_kA.txt']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

tes_p = {'Initial temperature':400,'Tank lenght':10,'Tank diameter':4,
    'Particle diameter':0.05,'Void fraction':0.4,'Solid density':2500,
    'Solid specific heat':1000,'Solid conductivity':1.5,
    'Wall thinckness':0.05,'Tank conductivity':15,
    'Insulation thickness':0.5,'Insulation conductivity':0.035,
    'HTF':'INCOMP::NaK'}
comp_p = {'ptc_A':2500,'ptc_aoi':0,'ptc_doc':1,'ptc_tamb':20,
    'eta_opt':0.75,'ptc_c_1':0,'ptc_c_2':0,'ptc_E':1000,
    'ptc_iam_1':0,'ptc_iam_2':0,'PR_Q':-1e6}
conn_p = {'5_T':520,'6_T':480,'6_p':50,'6_f':{'INCOMP::NaK':1},
    '13_p':5,'13_f':{'INCOMP::NaK':1},'15_p':5,'15_f':{'INCOMP::NaK':1}}

# --- DESIGN ---
sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys.tes.profile = np.ones(20)*400
sys.set_operation_mode(TESmode='1', current_irr=1000, mode='design',
    profile=sys.tes.profile, prev_TES_lay='Charge')
sys.conn_13.set_attr(T=400)  # TES secondary inlet

print('=== MODE 1 DESIGN ===')
print(f'Conns: {list(sys.network.conns.index)}')
try:
    sys.solve_network(mode='design', TESmode='1')
    conv = sys.network.converged
    print(f'Converged: {conv}')
    if conv:
        print(f'  CHX kA={sys.charge_tes_hx.kA.val:.0f}')
        print(f'  T02={sys.conn_02.T.val:.0f} T04={sys.conn_04.T.val:.0f} T09={sys.conn_09.T.val:.0f}')
        print(f'  T14={sys.conn_14.T.val:.0f} m14={sys.conn_14.m.val:.1f} kg/s')
        print(f'  Q_PTC={sys.ptc_field.Q.val/1e6:.2f} MW')
except Exception as e:
    print(f'FAILED: {str(e)[:120]}')

# --- OFFDESIGN at multiple E ---
print('\n=== MODE 1 OFFDESIGN ===')
solver = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
solver.initialize_modes()
solver.current_irr = 0

for E in [1000, 800, 600]:
    sys2 = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
        HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    sys2.tes.profile = np.ones(20)*450
    sys2.set_operation_mode(TESmode='1', current_irr=E, mode='offdesign',
        profile=sys2.tes.profile, prev_TES_lay='Charge')
    sys2.conn_13.set_attr(T=450)
    ok, _, _ = solver.attempt_to_solve(sys2, 'offdesign', 'base_design', '1', tries=5)
    if ok and sys2.network.converged:
        print(f'  E={E}: T02={sys2.conn_02.T.val:.0f} T14={sys2.conn_14.T.val:.0f} '
              f'Q_PTC={sys2.ptc_field.Q.val/1e6:.2f}MW m14={sys2.conn_14.m.val:.1f}')
    else:
        print(f'  E={E}: FAILED (mode={solver.current_mode})')
