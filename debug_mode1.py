"""Debug Mode 1 Parallel indirect convergence."""
from coreV5 import SolarThermalSystem, Solver
import numpy as np

tes_params = {
    'Initial temperature': 500,
    'Tank lenght': 10,
    'Tank diameter': 3,
    'Particle diameter': 0.05,
    'Void fraction': 0.4,
    'Solid density': 2500,
    'Solid specific heat': 1000,
    'Solid conductivity': 1.5,
    'Wall thinckness': 0.05,
    'Tank conductivity': 15,
    'Insulation thickness': 0.2,
    'Insulation conductivity': 0.05,
    'HTF': 'INCOMP::NaK',
}
component_params = {
    'ptc_A': 10000, 'ptc_aoi': 0.0, 'ptc_doc': 1.0, 'ptc_tamb': 20.0,
    'eta_opt': 0.75, 'ptc_c_1': 0.0, 'ptc_c_2': 0.0,
    'ptc_E': 1000.0, 'ptc_iam_1': 0.0, 'ptc_iam_2': 0.0,
    'PR_Q': -1e6,
}
conexion_params = {
    '5_T': 520, '6_T': 301, '6_p': 5, '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'INCOMP::NaK': 1},
    '15_p': 5, '15_f': {'INCOMP::NaK': 1},
}

print("=== Mode 1 Parallel Indirect ===")
sys = SolarThermalSystem(
    tes_params=tes_params, component_params=component_params,
    conexion_params=conexion_params, HTF='INCOMP::NaK',
    topology='Parallel', tank_config='indirect'
)
sys.create_network(mode=1)

# Check components
print(f"Components: charge_tes_hx={'yes' if hasattr(sys, 'charge_tes_hx') else 'no'}, "
      f"splitter1={'yes' if hasattr(sys, 'splitter1') else 'no'}, "
      f"merge2={'yes' if hasattr(sys, 'merge2') else 'no'}")

# Check connections
for cname in ['conn_01','conn_02','conn_04','conn_05','conn_06','conn_08',
              'conn_09','conn_10','conn_13','conn_14']:
    if hasattr(sys, cname):
        c = getattr(sys, cname)
        print(f"  {c.label}: {c.source.label} -> {c.target.label}")
    else:
        print(f"  {cname}: MISSING")

# Count parameters set
print(f"\nConnection parameters:")
for cname in ['conn_05','conn_06','conn_10','conn_13','conn_14']:
    if hasattr(sys, cname):
        c = getattr(sys, cname)
        flags = []
        if c.T.is_set: flags.append(f"T={c.T.val}")
        if c.p.is_set: flags.append(f"p={c.p.val}")
        if c.m.is_set: flags.append(f"m={c.m.val}")
        if c.fluid.is_set: flags.append(f"fluid={c.fluid.val}")
        print(f"  {c.label}: {', '.join(flags) if flags else 'no params set'}")

# Component params
print(f"\nComponent parameters:")
if hasattr(sys, 'charge_tes_hx'):
    hx = sys.charge_tes_hx
    flags = []
    if hx.pr1.is_set: flags.append(f"pr1={hx.pr1.val}")
    if hx.pr2.is_set: flags.append(f"pr2={hx.pr2.val}")
    if hx.Q.is_set: flags.append(f"Q={hx.Q.val}")
    print(f"  charge_tes_hx: {', '.join(flags) if flags else 'no params'}")
if hasattr(sys, 'process_hx'):
    flags = []
    if sys.process_hx.Q.is_set: flags.append(f"Q={sys.process_hx.Q.val}")
    if sys.process_hx.pr.is_set: flags.append(f"pr={sys.process_hx.pr.val}")
    print(f"  process_hx: {', '.join(flags) if flags else 'no params'}")
print(f"\nDone - all connections look good")
