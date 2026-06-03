import numpy as np
import os
from pbtes import SolarThermalSystem

# Define parameters
TES_P = {
    'Initial temperature': 400, 'Tank length': 10, 'Tank diameter': 3,
    'Particle diameter': 0.05, 'Void fraction': 0.4, 'Solid density': 2500,
    'Solid specific heat': 1000, 'Solid conductivity': 1.5, 'Wall thickness': 0.05,
    'Tank conductivity': 15, 'Insulation thickness': 0.2, 'Insulation conductivity': 0.05,
    'HTF': 'INCOMP::NaK'
}
COMP_P = {
    'ptc_A': 10000, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -1e6
}
CONN_P = {
    '5_T': 520, '6_T': 480, '6_p': 50, '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'INCOMP::NaK': 1}, '15_p': 5, '15_f': {'INCOMP::NaK': 1}
}

# Run design
print("--- RUNNING DESIGN POINT ---")
sys_d = SolarThermalSystem(tes_params=TES_P, component_params=COMP_P, conexion_params=CONN_P,
                            HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
profile = np.ones(20) * 400
sys_d.set_operation_mode(TESmode='1', current_irr=1000, profile=profile,
                          prev_TES_lay='Charge', mode='design')

# Enable logger output to console
import logging
logger = logging.getLogger('TESPyLogger')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)

sys_d.solve_network(mode='design', TESmode='1')
print(f"Design solved. PTC Area: {sys_d.ptc_field.A.val:.1f} m2, charge_hx_kA: {sys_d.charge_tes_hx.kA.val:.1f} W/K")

# Run offdesign
print("\n--- RUNNING OFFDESIGN POINT ---")
sys_o = SolarThermalSystem(tes_params=TES_P, component_params=COMP_P, conexion_params=CONN_P,
                            HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys_o.charge_hx_kA = sys_d.charge_tes_hx.kA.val
sys_o.ptc_field_A_designed = sys_d.ptc_field.A.val

sys_o.set_operation_mode(TESmode='1', current_irr=1000, profile=profile,
                          prev_TES_lay='Charge', mode='offdesign')

# Apply initial guesses and ranges to prevent NaN and singularities
sys_o.conn_14.T.max_val = 519.0
sys_o.conn_13.m.min_val = 0.5




print("\n--- Fixed connection attributes in offdesign: ---")
for conn_name in dir(sys_o):
    if conn_name.startswith('conn_'):
        conn = getattr(sys_o, conn_name, None)
        if conn is not None and hasattr(conn, 'label'):
            # Check which properties are set (fixed)
            fixed_props = []
            for prop in ['m', 'p', 'h', 'T', 'x']:
                val = getattr(conn, prop, None)
                if val is not None and val.is_set:
                    fixed_props.append(f"{prop}={val.val}")
            if fixed_props:
                print(f"Conn {conn.label}: {', '.join(fixed_props)}")

print("\n--- Fixed component attributes in offdesign: ---")
for comp_name in ['ptc_field', 'preheater_hx', 'process_hx', 'charge_tes_hx']:
    comp = getattr(sys_o, comp_name, None)
    if comp is not None:
        fixed_attrs = []
        for attr_name in ['A', 'E', 'Q', 'pr', 'pr1', 'pr2', 'kA', 'ttd_l']:
            attr = getattr(comp, attr_name, None)
            if attr is not None and attr.is_set:
                fixed_attrs.append(f"{attr_name}={attr.val}")
        print(f"Component {comp.label}: {', '.join(fixed_attrs)}")

try:
    print("\n--- Running offdesign with max_iter=1, init_path=None ---")
    kwargs = {'mode': 'offdesign', 'max_iter': 1, 'design_path': '.tespy_cache/base_design_1'}
    sys_o.network.solve(**kwargs)
except Exception as e:
    print(f"Offdesign max_iter=1 failed with: {e}")

print("\n--- Connection values after 1 iteration: ---")
for conn_name in dir(sys_o):
    if conn_name.startswith('conn_'):
        conn = getattr(sys_o, conn_name, None)
        if conn is not None and hasattr(conn, 'label'):
            print(f"Conn {conn.label:15}: m={conn.m.val:.3f} kg/s, p={conn.p.val:.3f} bar, T={conn.T.val:.3f} C")

try:
    print("\n--- Running full offdesign solve ---")
    kwargs = {'mode': 'offdesign', 'max_iter': 100, 'design_path': '.tespy_cache/base_design_1'}
    sys_o.network.solve(**kwargs)
    print(f"Full solve completed. Converged: {sys_o.network.converged}")
    print("\n--- Connection values after full solve: ---")
    for conn_name in dir(sys_o):
        if conn_name.startswith('conn_'):
            conn = getattr(sys_o, conn_name, None)
            if conn is not None and hasattr(conn, 'label'):
                print(f"Conn {conn.label:15}: m={conn.m.val:.3f} kg/s, p={conn.p.val:.3f} bar, T={conn.T.val:.3f} C")
except Exception as e:
    print(f"Full offdesign solve failed with: {e}")


