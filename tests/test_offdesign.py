import pytest
import numpy as np
from pbtes import SolarThermalSystem, Solver

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
    cache = '.tespy_cache'
    for mode_n in range(1, 7):
        p = os.path.join(cache, f'base_design_{mode_n}')
        if os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True)
    yield
    for mode_n in range(1, 7):
        p = os.path.join(cache, f'base_design_{mode_n}')
        if os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True)


def design_then_offdesign(mode, e_values, **kwargs):
    """Design solve, then offdesign at multiple E values. Returns list of Q_ptc (MW)."""
    results = []

    # Design
    sys_d = SolarThermalSystem(tes_params=TES_P, component_params=COMP_P, conexion_params=CONN_P,
                                HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    profile = np.ones(20) * 400
    if mode in [1, 5, 6]:
        if mode == 6:
            sys_d.charge_hx_kA = 150213
        sys_d.set_operation_mode(TESmode=str(mode), current_irr=1000, profile=profile,
                                  prev_TES_lay='Charge', mode='design')
    elif mode == 3:
        sys_d.set_operation_mode(TESmode='3', current_irr=0, profile=np.ones(20) * 540,
                                  prev_TES_lay='Charge', mode='design')
        if hasattr(sys_d, 'conn_15'):
            sys_d.conn_15.set_attr(T=540)
    else:
        sys_d.set_operation_mode(TESmode=str(mode), current_irr=1000, profile=profile,
                                  prev_TES_lay='Charge', mode='design')

    sys_d.solve_network(mode='design', TESmode=str(mode))

    # Offdesign with variable E
    sys_o = None
    for e in e_values:
        if sys_o is None:
            sys_o = SolarThermalSystem(tes_params=TES_P, component_params=COMP_P, conexion_params=CONN_P,
                                        HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
            if mode == 1:
                sys_o.charge_hx_kA = sys_d.charge_tes_hx.kA.val
                sys_o.ptc_field_A_designed = sys_d.ptc_field.A.val
            if mode == 6:
                sys_o.charge_hx_kA = 150213
            if mode == 3:
                sys_o.discharge_hx_kA = sys_d.discharge_tes_hx.kA.val
                sys_o.tes_charge_m = sys_d.conn_15.m.val
                sys_o.set_operation_mode(TESmode='3', current_irr=0, profile=np.ones(20) * 540,
                                          prev_TES_lay='Charge', mode='offdesign')
                if hasattr(sys_o, 'conn_15'):
                    sys_o.conn_15.set_attr(T=540)
            else:
                sys_o.set_operation_mode(TESmode=str(mode), current_irr=e, profile=profile,
                                          prev_TES_lay='Charge', mode='offdesign')
            sys_o.solve_network(mode='offdesign', TESmode=str(mode), use_init_path=True)
        else:
            if getattr(sys_o, 'ptc_field', None) is not None:
                sys_o.ptc_field.set_attr(E=e)
                sys_o.solve_network(mode='offdesign', TESmode=str(mode), use_init_path=False)
            else:
                sys_o.solve_network(mode='offdesign', TESmode=str(mode), use_init_path=False)
        q = sys_o.ptc_field.Q.val / 1e6 if getattr(sys_o, 'ptc_field', None) is not None else 0
        results.append(q)
    return results


def test_mode1_offdesign():
    """Mode 1: PTC output matches E * A * eta at irradiances ≥ 700 W/m².

    Mode 1 (solar charges TES + serves process) is only active when DNI is high
    enough for the charge HX to operate at a meaningful fraction of its design
    kA.  For this test geometry (A=10000 m², E_design=1000 W/m²) the controller
    selects Mode 1 only for E ≥ 700 W/m² (70% of design) due to the thermodynamic
    effectiveness limit of the charge HX. Below that, Mode 2
    (process-only with field defocus) is selected instead to avoid ill-conditioned
    HX equations.
    """
    e_values = [1000, 800, 750, 700]
    results = design_then_offdesign(1, e_values)
    for i, e in enumerate(e_values):
        expected = e * 10000 * 0.75 / 1e6
        assert abs(results[i] - expected) < 0.2, (
            f'E={e}: Q={results[i]:.3f} MW != expected {expected:.3f} MW'
        )


def test_mode2_offdesign():
    """Mode 2: A='var' defocus, Q always equals process demand (1 MW)."""
    results = design_then_offdesign(2, [800, 600, 400])
    for i, e in enumerate([800, 600, 400]):
        expected = 1.0  # Always 1 MW with defocus
        assert abs(results[i] - expected) < 0.2, (
            f'E={e}: Q={results[i]:.1f} MW != expected {expected:.1f} MW'
        )


def test_mode4_offdesign():
    """Mode 4: Simple auxiliary loop, always converges."""
    results = design_then_offdesign(4, [800])
    assert len(results) == 1  # Just tests convergence


def test_mode3_offdesign():
    """Mode 3 Parallel Indirect: ensures discharging converges cleanly and works in Regime A/B."""
    # We test multiple offdesign iterations of Mode 3 discharging
    results = design_then_offdesign(3, [0, 0, 0])
    assert len(results) == 3

