"""Debug Mode 2 offdesign after create_network refactor."""
import os, shutil, numpy as np
for f in ['base_design_2','base_design_4']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

from coreV5 import SolarThermalSystem, Solver

tes_p = {'Initial temperature': 400, 'Tank lenght': 10, 'Tank diameter': 3,
    'Particle diameter': 0.05, 'Void fraction': 0.4, 'Solid density': 2500,
    'Solid specific heat': 1000, 'Solid conductivity': 1.5,
    'Wall thinckness': 0.05, 'Tank conductivity': 15,
    'Insulation thickness': 0.2, 'Insulation conductivity': 0.05,
    'HTF': 'INCOMP::NaK'}
comp_p = {'ptc_A': 2500, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -1e6}
conn_p = {'5_T': 520, '6_T': 480, '6_p': 50, '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'INCOMP::NaK': 1}, '15_p': 5, '15_f': {'INCOMP::NaK': 1}}

# Design Mode 2
sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys.create_network(mode=2, design_mode='design')
sys.tes.profile = np.ones(20) * 500
sys.set_operation_mode(TESmode='2', current_irr=1000, mode='design',
    profile=sys.tes.profile, prev_TES_lay='Charge')
sys.solve_network(mode='design', TESmode='2')
print(f'Mode 2 design: converged={sys.network.converged}, A={sys.ptc_field.A.val:.0f}')

# Offdesign with E=600
sys2 = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys2.create_network(mode=2, design_mode='offdesign')  # NEW: design_mode='offdesign'
sys2.tes.profile = np.ones(20) * 500
sys2.set_operation_mode(TESmode='2', current_irr=600, mode='offdesign',
    profile=sys2.tes.profile, prev_TES_lay='Charge')

# Check what constraints are set
print(f'\nPTC field attributes:')
for attr in ['A', 'E', 'eta_opt']:
    a = getattr(sys2.ptc_field, attr, None)
    if a is not None:
        print(f'  {attr}: is_set={a.is_set}, val={a.val}')
print(f'conn_05.T is_set={sys2.conn_05.T.is_set}, val={sys2.conn_05.T.val}')
print(f'conn_06.T is_set={sys2.conn_06.T.is_set}, val={sys2.conn_06.T.val}')
print(f'PH Q is_set={sys2.preheater_hx.Q.is_set}, val={sys2.preheater_hx.Q.val if sys2.preheater_hx.Q.val is not None else None}')
print(f'PR Q is_set={sys2.process_hx.Q.is_set}, val={sys2.process_hx.Q.val}')

try:
    sys2.solve_network(mode='offdesign', design_path='base_design_2', TESmode='2')
    print(f'\nMode 2 offdesign: converged={sys2.network.converged}')
    if sys2.network.converged:
        print(f'  A={sys2.ptc_field.A.val:.0f} T02={sys2.conn_02.T.val:.0f} m={sys2.conn_06.m.val:.1f}')
except Exception as e:
    print(f'\nMode 2 offdesign FAILED: {str(e)[:120]}')
