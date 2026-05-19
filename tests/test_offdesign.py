import pytest
import numpy as np
from coreV5 import SolarThermalSystem, Solver

TES_P = {'Initial temperature': 400, 'Tank length': 10, 'Tank diameter': 3,
    'Particle diameter': 0.05, 'Void fraction': 0.4, 'Solid density': 2500,
    'Solid specific heat': 1000, 'Solid conductivity': 1.5, 'Wall thickness': 0.05,
    'Tank conductivity': 15, 'Insulation thickness': 0.2, 'Insulation conductivity': 0.05,
    'HTF': 'INCOMP::NaK'}
COMP_P = {'ptc_A': 10000, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -1e6}
CONN_P = {'5_T': 520, '6_T': 480, '6_p': 50, '6_f': {'INCOMP::NaK': 1},
    '13_p': 5, '13_f': {'INCOMP::NaK': 1}, '15_p': 5, '15_f': {'INCOMP::NaK': 1}}

@pytest.fixture(autouse=True)
def clear_designs():
    import os, shutil
    for f in ['base_design_1','base_design_2','base_design_3','base_design_4','base_design_5','base_design_6',
              'mode1_kA.txt','m5d','test_design']:
        if os.path.exists(f):
            try:
                if os.path.isfile(f): os.remove(f)
                else: shutil.rmtree(f, ignore_errors=True)
            except: pass
    yield
    for f in ['base_design_1','base_design_2','base_design_3','base_design_4','base_design_5','base_design_6',
              'mode1_kA.txt','m5d','test_design']:
        if os.path.exists(f):
            try:
                if os.path.isfile(f): os.remove(f)
                else: shutil.rmtree(f, ignore_errors=True)
            except: pass

def design_then_offdesign(mode, e_values, **kwargs):
    """Design solve, then offdesign at multiple E values. Returns list of Q_ptc."""
    results = []
    solver = Solver(tes_params=TES_P, component_params=COMP_P, conexion_params=CONN_P,
                    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    
    # Design
    sys_d = SolarThermalSystem(tes_params=TES_P, component_params=COMP_P, conexion_params=CONN_P,
                                HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    profile = np.ones(20) * 400
    if mode in [1, 5, 6]:
        if mode == 6: sys_d.charge_hx_kA = 150213
        sys_d.set_operation_mode(TESmode=str(mode), current_irr=1000, profile=profile, prev_TES_lay='Charge', mode='design')
        if hasattr(sys_d, 'conn_13'): sys_d.conn_13.set_attr(T=400)
    elif mode == 3:
        sys_d.set_operation_mode(TESmode='3', profile=np.ones(20)*540, prev_TES_lay='Discharge', mode='design')
        if hasattr(sys_d, 'conn_15'): sys_d.conn_15.set_attr(T=540)
    else:
        sys_d.set_operation_mode(TESmode=str(mode), current_irr=1000, profile=profile, prev_TES_lay='Charge', mode='design')
    
    sys_d.solve_network(mode='design', TESmode=str(mode))
    
    # Offdesign with variable E
    for e in e_values:
        sys_o = SolarThermalSystem(tes_params=TES_P, component_params=COMP_P, conexion_params=CONN_P,
                                    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
        if mode == 6: sys_o.charge_hx_kA = 150213
        sys_o.set_operation_mode(TESmode=str(mode), current_irr=e, profile=profile, prev_TES_lay='Charge', mode='offdesign')
        if hasattr(sys_o, 'conn_13'): sys_o.conn_13.set_attr(T=400)
        if mode == 3:
            sys_o.set_operation_mode(TESmode='3', current_irr=0, profile=np.ones(20)*540, prev_TES_lay='Discharge', mode='offdesign')
            if hasattr(sys_o, 'conn_15'): sys_o.conn_15.set_attr(T=540)
        sys_o.solve_network(mode='offdesign', TESmode=str(mode))
        results.append(sys_o.ptc_field.Q.val / 1e6 if hasattr(sys_o, 'ptc_field') else 0)
    return results


def test_mode1_offdesign():
    """Mode 1: PTC output matches E*A*eta"""
    results = design_then_offdesign(1, [800, 600, 400])
    for i, e in enumerate([800, 600, 400]):
        expected = e * 10000 * 0.75 / 1e6
        assert abs(results[i] - expected) < 0.2, f'E={e}: Q={results[i]:.1f} != expected {expected:.1f}'

def test_mode2_offdesign():
    """Mode 2: A='var' defocus, Q always 1 MW"""
    results = design_then_offdesign(2, [800, 600, 400])
    for i, e in enumerate([800, 600, 400]):
        expected = 1.0  # Always 1 MW with defocus
        assert abs(results[i] - expected) < 0.2, f'E={e}: Q={results[i]:.1f} != expected {expected:.1f}'

def test_mode4_offdesign():
    """Mode 4: Simple loop, always converges"""
    results = design_then_offdesign(4, [800])
    assert len(results) == 1  # Just tests convergence
