import pytest
import pandas as pd
import numpy as np
from pbtes import Solver
from pbtes.config import baseline_config

def test_inhouse_ptc_initialization():
    """
    Test that the solver initializes, designs the loops, and resolves the network
    correctly when the use_inhouse_ptc option is enabled.
    """
    tes_p, comp_p, conn_p = baseline_config()
    
    # Enable the in-house model
    comp_p['use_inhouse_ptc'] = True
    comp_p['ptc_mode'] = 'constant_T_out'
    comp_p['ptc_T_out_target'] = 560.0
    
    # Lower process demand and PTC area to run a small test quickly
    comp_p['ptc_A'] = 1000.0
    
    solver = Solver(
        tes_params=tes_p,
        component_params=comp_p,
        conexion_params=conn_p,
        HTF='INCOMP::NaK',
        system_mode='Full',
        topology='Parallel',
        tank_config='indirect'
    )
    
    # Check that PTC model was initialized and designed
    assert solver.use_inhouse_ptc is True
    assert solver.ptc_model is not None
    assert solver.ptc_model.is_designed is True
    assert solver.ptc_model.N_loops_real > 0
    assert solver.ptc_model.N_PTC_real > 0
    
    # Run design initialization for all modes
    solver.initialize_modes()
    
    # Verify design parameters were persisted
    assert solver.charge_hx_kA is not None
    assert solver.discharge_hx_kA is not None


def test_inhouse_ptc_quasi_steady():
    """
    Test that the transient simulation runs successfully with the in-house PTC model.
    """
    tes_p, comp_p, conn_p = baseline_config()
    comp_p['use_inhouse_ptc'] = True
    comp_p['ptc_A'] = 1000.0
    
    solver = Solver(
        tes_params=tes_p,
        component_params=comp_p,
        conexion_params=conn_p,
        HTF='INCOMP::NaK',
        system_mode='Full',
        topology='Parallel',
        tank_config='indirect'
    )
    
    solver.initialize_modes()
    
    # Simulate a single day
    results = solver.run_quasi_steady_simulation(days_to_simulate=1, csv='TMY.csv')
    
    assert len(results) == 24
    
    df = pd.DataFrame(results)
    
    # Verify that the network converged in all steps or fell back cleanly
    assert df['network_converged'].all()
    
    # Verify that during active solar modes, PTC mass flow and outlet temperature are physical
    solar_hours = df[df['TESmode'].astype(str).isin(['1', '2', '5', '6'])]
    non_solar_hours = df[df['TESmode'].astype(str).isin(['3', '4'])]
    
    if not solar_hours.empty:
        assert (solar_hours['mdot_ptc_kg_s'] > 0).all()
        assert (solar_hours['T_ptc_out'] > 400.0).all()
        
    if not non_solar_hours.empty:
        assert (non_solar_hours['mdot_ptc_kg_s'] == 0).all()


def test_sd_inhouse_ptc_quasi_steady():
    """
    Test that the transient simulation runs successfully for Series/Direct layout with in-house PTC.
    """
    tes_p, comp_p, conn_p = baseline_config()
    comp_p['use_inhouse_ptc'] = True
    comp_p['ptc_A'] = 1000.0
    
    solver = Solver(
        tes_params=tes_p,
        component_params=comp_p,
        conexion_params=conn_p,
        HTF='INCOMP::NaK',
        system_mode='Full',
        topology='Series',
        tank_config='direct'
    )
    
    solver.initialize_modes()
    
    # Simulate a single day
    results = solver.run_quasi_steady_simulation(days_to_simulate=1, csv='TMY.csv')
    
    assert len(results) == 24
    
    df = pd.DataFrame(results)
    
    # Verify that the network converged in all steps or fell back cleanly
    assert df['network_converged'].all()
    
    solar_hours = df[df['TESmode'].astype(str).isin(['1', '2'])]
    non_solar_hours = df[df['TESmode'].astype(str).isin(['3', '4'])]
    
    if not solar_hours.empty:
        assert (solar_hours['mdot_ptc_kg_s'] > 0).all()
        assert (solar_hours['T_ptc_out'] > 400.0).all()
        
    if not non_solar_hours.empty:
        assert (non_solar_hours['mdot_ptc_kg_s'] == 0).all()


def test_pi_inhouse_modes():
    """Validate offdesign convergence for all Modes 1-6 in Parallel/Indirect layout with in-house PTC."""
    tes_p, comp_p, conn_p = baseline_config()
    comp_p['use_inhouse_ptc'] = True
    comp_p['ptc_A'] = 1000.0
    
    solver = Solver(
        tes_params=tes_p,
        component_params=comp_p,
        conexion_params=conn_p,
        HTF='INCOMP::NaK',
        system_mode='Full',
        topology='Parallel',
        tank_config='indirect'
    )
    solver.initialize_modes()
    
    # Mode 1: Charge + Process
    solver.current_irr = 1000.0
    solver.solar_system.set_operation_mode(TESmode='1', current_irr=1000.0, profile=np.ones(20)*450.0, prev_TES_lay='Charge', mode='offdesign')
    iter_info = solver._iterate_tes_coupling(mode='offdesign', system=solver.solar_system, TESmode='1', design_path='base_design_1', Tamb=20.0)
    assert iter_info['status'] == 'converged'
    assert solver.solar_system.network.converged
    
    # Mode 2: Solar to Process
    solver.current_irr = 800.0
    solver.solar_system.set_operation_mode(TESmode='2', current_irr=800.0, profile=np.ones(20)*450.0, prev_TES_lay='Charge', mode='offdesign')
    iter_info = solver._iterate_tes_coupling(mode='offdesign', system=solver.solar_system, TESmode='2', design_path='base_design_2', Tamb=20.0)
    assert iter_info['status'] == 'converged'
    assert solver.solar_system.network.converged

    # Mode 3: TES Discharge
    solver.current_irr = 0.0
    solver.solar_system.set_operation_mode(TESmode='3', current_irr=0.0, profile=np.ones(20)*540.0, prev_TES_lay='Charge', mode='offdesign')
    iter_info = solver._iterate_tes_coupling(mode='offdesign', system=solver.solar_system, TESmode='3', design_path='base_design_3', Tamb=20.0)
    assert iter_info['status'] == 'converged'
    assert solver.solar_system.network.converged

    # Mode 4: Standby
    solver.current_irr = 0.0
    solver.solar_system.set_operation_mode(TESmode='4', current_irr=0.0, profile=np.ones(20)*450.0, prev_TES_lay='Charge', mode='offdesign')
    iter_info = solver._iterate_tes_coupling(mode='offdesign', system=solver.solar_system, TESmode='4', design_path='base_design_4', Tamb=20.0)
    assert iter_info['status'] == 'converged'
    assert solver.solar_system.network.converged

    # Mode 5: High-T charge
    solver.current_irr = 900.0
    solver.solar_system.set_operation_mode(TESmode='5', current_irr=900.0, profile=np.ones(20)*400.0, prev_TES_lay='Charge', mode='offdesign')
    iter_info = solver._iterate_tes_coupling(mode='offdesign', system=solver.solar_system, TESmode='5', design_path='base_design_5', Tamb=20.0)
    assert iter_info['status'] == 'converged'
    assert solver.solar_system.network.converged

    # Mode 6: Decoupled charge
    solver.current_irr = 1000.0
    solver.solar_system.set_operation_mode(TESmode='6', current_irr=1000.0, profile=np.ones(20)*400.0, prev_TES_lay='Charge', mode='offdesign')
    iter_info = solver._iterate_tes_coupling(mode='offdesign', system=solver.solar_system, TESmode='6', design_path='base_design_6', Tamb=20.0)
    assert iter_info['status'] == 'converged'
    assert solver.solar_system.network.converged


def test_sd_inhouse_modes():
    """Validate offdesign convergence for all Modes 1-4 in Series/Direct layout with in-house PTC."""
    tes_p, comp_p, conn_p = baseline_config()
    comp_p['use_inhouse_ptc'] = True
    comp_p['ptc_A'] = 1000.0
    
    solver = Solver(
        tes_params=tes_p,
        component_params=comp_p,
        conexion_params=conn_p,
        HTF='INCOMP::NaK',
        system_mode='Full',
        topology='Series',
        tank_config='direct'
    )
    solver.initialize_modes()
    
    # Mode 1: Charge + Process
    solver.current_irr = 1000.0
    solver.solar_system.hot_tes.profile = np.ones(20) * 520.0
    solver.solar_system.cold_tes.profile = np.ones(20) * 440.0
    solver.solar_system.set_operation_mode(TESmode='1', current_irr=1000.0, profile=None, prev_TES_lay='Charge', mode='design')
    iter_info = solver._iterate_tes_coupling(mode='offdesign', system=solver.solar_system, TESmode='1', design_path='base_design_1', Tamb=20.0)
    assert iter_info['status'] == 'converged'
    assert solver.solar_system.network.converged
    
    # Mode 2: Solar to Process
    solver.current_irr = 800.0
    solver.solar_system.set_operation_mode(TESmode='2', current_irr=800.0, profile=np.ones(20)*450.0, prev_TES_lay='Charge', mode='offdesign')
    iter_info = solver._iterate_tes_coupling(mode='offdesign', system=solver.solar_system, TESmode='2', design_path='base_design_2', Tamb=20.0)
    assert iter_info['status'] == 'converged'
    assert solver.solar_system.network.converged

    # Mode 3: TES Discharge
    solver.current_irr = 0.0
    solver.solar_system.hot_tes.profile = np.ones(20) * 540.0
    solver.solar_system.cold_tes.profile = np.ones(20) * 440.0
    solver.solar_system.set_operation_mode(TESmode='3', current_irr=0.0, profile=solver.solar_system.hot_tes.profile, prev_TES_lay='Charge', mode='offdesign')
    iter_info = solver._iterate_tes_coupling(mode='offdesign', system=solver.solar_system, TESmode='3', design_path='base_design_4', Tamb=20.0)
    assert iter_info['status'] == 'converged'
    assert solver.solar_system.network.converged

    # Mode 4: Standby
    solver.current_irr = 0.0
    solver.solar_system.set_operation_mode(TESmode='4', current_irr=0.0, profile=np.ones(20)*450.0, prev_TES_lay='Charge', mode='offdesign')
    iter_info = solver._iterate_tes_coupling(mode='offdesign', system=solver.solar_system, TESmode='4', design_path='base_design_4', Tamb=20.0)
    assert iter_info['status'] == 'converged'
    assert solver.solar_system.network.converged

