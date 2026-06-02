import pytest
from pbtes import SolarThermalSystem

# Basic parameters for testing
# These can be expanded later if needed
TES_PARAMS = {
    'Initial temperature': 400,
    'Tank length': 10,
    'Tank diameter': 3,
    'Particle diameter': 0.05,
    'Void fraction': 0.4,
    'Solid density': 2300,
    'Solid specific heat': 1000,
    'Solid conductivity': 0.5,
    'Wall thickness': 0.05,
    'Tank conductivity': 15,
    'Insulation thickness': 0.1,
    'Insulation conductivity': 0.04,
    'HTF': 'INCOMP::NaK'
}

COMPONENT_PARAMS = {
    'ptc_A': 2500,
    'ptc_aoi': 0,
    'ptc_doc': 0,
    'ptc_tamb': 25,
    'eta_opt': 0.8,
    'ptc_c_1': 0.05,
    'ptc_c_2': 0.0002,
    'ptc_E': 1000,
    'ptc_iam_1': 0.0,
    'ptc_iam_2': 0.0,
    'PR_Q': -10e6
}

CONEXION_PARAMS = {
    '5_T': 520,
    '6_T': 400,
    '6_p': 5,
    '6_f': {'INCOMP::NaK': 1.0},
    '13_p': 5,
    '13_f': {'INCOMP::NaK': 1.0},
    '15_p': 5,
    '15_f': {'INCOMP::NaK': 1.0},
}

@pytest.fixture
def system_fixture():
    """
    Provides a fresh, isolated instance of SolarThermalSystem for each test.
    """
    system = SolarThermalSystem(
        tes_params=TES_PARAMS,
        component_params=COMPONENT_PARAMS,
        conexion_params=CONEXION_PARAMS,
        HTF='INCOMP::NaK',
        topology='Parallel'
    )
    return system

def test_fixture_creation(system_fixture):
    """
    Tests that the fixture is created correctly.
    """
    assert isinstance(system_fixture, SolarThermalSystem)
    assert system_fixture.network is None

@pytest.mark.parametrize("mode", [1, 2, 3, 4, 5, 6])
def test_create_network_for_modes(system_fixture, mode):
    """
    Tests that the network is created successfully for each specified mode.
    """
    system_fixture.create_network(mode=mode)
    assert system_fixture.network is not None
    assert isinstance(system_fixture.network, object) # A basic check for a TESPy network object

def test_solver_mode1_precalculation_areas():
    """
    Tests that Solver.initialize_modes() converges for small and large PTC areas
    using the new pre-calculation and scaling logic.
    """
    from pbtes.simulation.solver import Solver
    from pbtes.config import baseline_config
    
    # Get baseline config
    tes_p, comp_p, conn_p = baseline_config()
    
    # Test with very small PTC area (500 m2)
    comp_p_small = comp_p.copy()
    comp_p_small['ptc_A'] = 500.0
    solver_small = Solver(tes_p, comp_p_small, conn_p, HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    solver_small.initialize_modes()
    assert solver_small.charge_hx_kA is not None
    assert solver_small.charge_hx_kA > 0.0
    
    # Test with very large PTC area (3000 m2)
    comp_p_large = comp_p.copy()
    comp_p_large['ptc_A'] = 3000.0
    solver_large = Solver(tes_p, comp_p_large, conn_p, HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    solver_large.initialize_modes()
    assert solver_large.charge_hx_kA is not None
    assert solver_large.charge_hx_kA > 0.0
