"""
test_networks.py

Validates that all 10 network configurations (5 modes × 2 topologies)
build correctly before attempting to solve them.

Mode legend:
  1 - PTC to Process AND TES (charging)
  2 - PTC to Process only (standby TES)
  3 - TES to Process (discharging)
  4 - Standby (auxiliary to Process)
  6 - PTC full to TES (auxiliary to Process)
"""

import pytest
from pbtes import SolarThermalSystem


def _make_params(topology, tank_config='indirect'):
    """Minimal valid parameters for network construction."""
    tes_params = {
        'Initial temperature': 500,
        'Tank length': 10,
        'Tank diameter': 3,
        'Particle diameter': 0.05,
        'Void fraction': 0.4,
        'Solid density': 2500,
        'Solid specific heat': 1000,
        'Solid conductivity': 1.5,
        'Wall thickness': 0.05,
        'Tank conductivity': 15,
        'Insulation thickness': 0.2,
        'Insulation conductivity': 0.05,
        'HTF': 'INCOMP::NaK',
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
        'PR_Q': -1e6,
    }
    conexion_params = {
        '5_T': 520,
        '6_T': 301,
        '6_p': 5,
        '6_f': {'INCOMP::NaK': 1},
        '13_p': 5,
        '13_f': {'INCOMP::NaK': 1},
        '15_p': 5,
        '15_f': {'INCOMP::NaK': 1},
    }
    return SolarThermalSystem(
        rows=1,
        tes_params=tes_params,
        component_params=component_params,
        conexion_params=conexion_params,
        HTF='INCOMP::NaK',
        topology=topology,
        tank_config=tank_config,
    )


# ── Mode-specific connection verification ──────────────────────────

def _assert_parallel_mode1(system, tank_config):
    """Mode 1 Parallel: PTC → Split → (Process + Tank) → Merge → CC"""
    assert hasattr(system, 'splitter1'), "Missing splitter"
    assert hasattr(system, 'merge2'), "Missing merge"
    assert system.conn_02.target.label == 'Splitter1'
    assert system.conn_04.source.label == 'Splitter1'
    assert system.conn_09.source.label == 'Splitter1'
    assert system.conn_06.target.label == 'Merge2'
    assert system.conn_10.target.label == 'Merge2'
    if tank_config == 'indirect':
        assert hasattr(system, 'tes_ch_source')
        assert hasattr(system, 'conn_13')
        assert hasattr(system, 'conn_14')


def _assert_series_mode1(system, tank_config):
    """Mode 1 Series: PTC -> Process -> Tank -> CC (indirect);
       Mode 1 Series/Direct: PTC -> HotTankHX -> Process -> ColdTankHX -> CC"""
    assert not hasattr(system, 'splitter1')
    assert not hasattr(system, 'merge2')
    if tank_config == 'direct':
        assert hasattr(system, 'hot_tank_hx')
        assert hasattr(system, 'cold_tank_hx')
        assert system.conn_02.target.label == 'Hot_Tank_Pipe'
        assert system.conn_06.target.label == 'Cold_Tank_Pipe'
    else:
        assert system.conn_02.target.label == 'Preheater_HX'
        assert system.conn_06.target.label in ('Charge_TES_HX', 'Charge_TES_Pipe')
        assert hasattr(system, 'conn_13')
        assert hasattr(system, 'conn_14')


def _assert_mode2(system, tank_config):
    """Mode 2: PTC → Process → CC (no tank interaction)"""
    assert system.conn_02.target.label == 'Preheater_HX'
    assert system.conn_06.target.label == 'CycleCloser'


def _assert_mode3(system, tank_config):
    """Mode 3: Tank → Process → CC → Tank (discharging)"""
    assert hasattr(system, 'discharge_tes_hx')
    if tank_config == 'indirect':
        assert hasattr(system, 'tes_dch_source')
        assert hasattr(system, 'conn_15')
        assert hasattr(system, 'conn_16')


def _assert_mode4(system, tank_config):
    """Mode 4: Aux → Process → CC (standby)"""
    assert system.conn_04.source.label == 'CycleCloser'
    assert system.conn_04.target.label == 'Preheater_HX'
    assert system.conn_05.target.label == 'Process_HX'


def _assert_parallel_mode6(system, tank_config):
    """Mode 6 Parallel: two independent cycles, PTC→TES + CC2→PH→PR→CC2"""
    assert hasattr(system, 'cycle_closer2')
    if tank_config == 'indirect':
        assert hasattr(system, 'conn_13')
        assert hasattr(system, 'conn_14')


def _assert_series_mode6(system, tank_config):
    """Mode 6 Series: PTC → Tank → CC"""
    assert not hasattr(system, 'cycle_closer2')
    if tank_config == 'indirect':
        assert hasattr(system, 'conn_13')
        assert hasattr(system, 'conn_14')


def _assert_mode5(system, tank_config):
    """Mode 5: High-T charge (PTC → high_t_charge_hx → PH → PR → CC)"""
    assert hasattr(system, 'high_t_charge_hx'), "Missing high_t_charge_hx (Mode 5 HX)"
    assert not hasattr(system, 'splitter1') and not hasattr(system, 'merge2')
    if tank_config == 'indirect':
        assert hasattr(system, 'conn_13')
        assert hasattr(system, 'conn_14')


MODE_ASSERTIONS = {
    ('Parallel', 1): _assert_parallel_mode1,
    ('Series', 1):   _assert_series_mode1,
    ('Parallel', 2): _assert_mode2,
    ('Series', 2):   _assert_mode2,
    ('Parallel', 3): _assert_mode3,
    ('Series', 3):   _assert_mode3,
    ('Parallel', 4): _assert_mode4,
    ('Series', 4):   _assert_mode4,
    ('Parallel', 6): _assert_parallel_mode6,
    ('Series', 6):   _assert_series_mode6,
    ('Parallel', 5): _assert_mode5,
    ('Series', 5):   _assert_mode5,
}

TEST_GRID = []
for tank in ('indirect', 'direct'):
    for topo in ('Parallel', 'Series'):
        for mode in (1, 2, 3, 4, 5, 6):
            TEST_GRID.append((tank, topo, mode))


@pytest.mark.parametrize("tank_config,topology,mode", TEST_GRID)
def test_network_builds(tank_config, topology, mode):
    """Build the network and verify correct topology."""
    system = _make_params(topology, tank_config)
    system.create_network(mode)

    assert system.network is not None, "Network not created"

    assert_fn = MODE_ASSERTIONS.get((topology, mode))
    if assert_fn:
        assert_fn(system, tank_config)

    conn_count = len(system.network.conns.index)
    assert conn_count > 0, "Network has no connections"
    print(f"  [OK] {tank_config} {topology} Mode {mode}: {conn_count} conns")
