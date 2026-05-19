import pytest
from coreV5 import SolarThermalSystem, Solver
import CoolProp.CoolProp as cp
import numpy as np

@pytest.fixture
def base_params():
    tes_params = {
        'Initial temperature': 400,
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
        'HTF': 'INCOMP::NaK'
    }
    
    component_params = {
        'ptc_A': 10000,
        'ptc_aoi': 0.0,
        'ptc_doc': 1.0,
        'ptc_tamb': 20.0,
        'eta_opt': 0.75,
        'ptc_c_1': 0.0,
        'ptc_c_2': 0.0,
        'ptc_E': 1000.0,
        'ptc_iam_1': 0.0,
        'ptc_iam_2': 0.0,
        'PR_Q': -1e6
    }
    
    conexion_params = {
        '5_T': 520,
        '6_T': 480,
        '6_p': 50,
        '6_f': {'INCOMP::NaK': 1},
        '13_p': 5,
        '13_f': {'INCOMP::NaK': 1},
        '15_p': 5,
        '15_f': {'INCOMP::NaK': 1},
    }
    
    return {
        'tes_params': tes_params,
        'component_params': component_params,
        'conexion_params': conexion_params,
        'HTF': 'INCOMP::NaK'
    }

@pytest.fixture
def system_parallel(base_params):
    params = base_params.copy()
    params['topology'] = 'Parallel'
    return SolarThermalSystem(**params)

@pytest.fixture
def system_series(base_params):
    params = base_params.copy()
    params['topology'] = 'Series'
    return SolarThermalSystem(**params)

def test_parallel_isolation(system_parallel):
    system_parallel.create_network(mode=1)
    
    # Assert specific parallel connections are present
    assert hasattr(system_parallel, 'conn_04')
    assert hasattr(system_parallel, 'conn_08')
    assert hasattr(system_parallel, 'conn_09')
    
    # Check that it's connected correctly
    assert system_parallel.conn_06.target.label == 'Merge2'

def test_series_isolation(system_series):
    system_series.create_network(mode=1)
    
    # Assert specific parallel connections do NOT exist
    assert not hasattr(system_series, 'conn_04')
    assert not hasattr(system_series, 'conn_08')
    assert not hasattr(system_series, 'conn_09')
    
    # Check that conn_06 connects process_hx out to charge_tes_pipe
    assert system_series.conn_06.target.label == 'Charge_TES_HX'

def test_parallel_thermodynamics(base_params):
    params = base_params.copy()
    params['topology'] = 'Parallel'
    
    sys = SolarThermalSystem(tes_params=params['tes_params'],
                             component_params=params['component_params'],
                             conexion_params=params['conexion_params'],
                             HTF=params['HTF'],
                             topology=params['topology'])
    profile = np.ones(20) * params['tes_params']['Initial temperature']
    sys.set_operation_mode(TESmode='1', current_irr=1000, profile=profile, prev_TES_lay='Charge', mode='design')
    sys.conn_13.set_attr(T=profile[-1])
    sys.network.solve('design', max_iter=100)
    
    # Parallel mass balance
    m_ptc = sys.conn_02.m.val_SI
    m_pr = sys.conn_04.m.val_SI
    m_tes = sys.conn_09.m.val_SI
    
    assert abs(m_ptc - (m_pr + m_tes)) < 1e-4, f'{m_ptc:.3f} != {m_pr:.3f} + {m_tes:.3f}'
    
    h_in_pr = cp.PropsSI('H', 'T', sys.conn_05.T.val_SI, 'P', sys.conn_05.p.val_SI, params['HTF'])
    h_out_pr = cp.PropsSI('H', 'T', sys.conn_06.T.val_SI, 'P', sys.conn_06.p.val_SI, params['HTF'])
    Q_pr_expected = m_pr * (h_in_pr - h_out_pr)
    
    assert abs(abs(Q_pr_expected) - abs(sys.process_hx.Q.val)) < 1.0

def test_series_thermodynamics(base_params):
    params = base_params.copy()
    params['topology'] = 'Series'
    
    sys = SolarThermalSystem(tes_params=params['tes_params'],
                             component_params=params['component_params'],
                             conexion_params=params['conexion_params'],
                             HTF=params['HTF'],
                             topology=params['topology'])
    profile = np.ones(20) * params['tes_params']['Initial temperature']
    sys.set_operation_mode(TESmode='1', current_irr=1000, profile=profile, prev_TES_lay='Charge', mode='design')
    sys.conn_13.set_attr(T=profile[-1])
    sys.network.solve('design', max_iter=100)
    
    # Series mass balance
    m_ptc = sys.conn_01.m.val_SI
    m_pr = sys.conn_05.m.val_SI
    m_tes = sys.conn_06.m.val_SI
    
    assert abs(m_ptc - m_pr) < 1e-4, f'{m_ptc:.3f} != {m_pr:.3f}'
    assert abs(m_pr - m_tes) < 1e-4, f'{m_pr:.3f} != {m_tes:.3f}'
    
    h_in_pr = cp.PropsSI('H', 'T', sys.conn_05.T.val_SI, 'P', sys.conn_05.p.val_SI, params['HTF'])
    h_out_pr = cp.PropsSI('H', 'T', sys.conn_06.T.val_SI, 'P', sys.conn_06.p.val_SI, params['HTF'])
    Q_pr_expected = m_pr * (h_in_pr - h_out_pr)
    
    assert abs(abs(Q_pr_expected) - abs(sys.process_hx.Q.val)) < 1.0
