import pytest
import pandas as pd
from datetime import datetime
from pbtes.storage.zinc_pool import ZincPool

def test_zinc_pool_init_defaults():
    pool = ZincPool()
    assert pool.mass == 150e3
    assert pool.temperature == 450
    assert pool.cp == 512
    assert pool.UA == 500
    assert pool.target == 450
    assert pool.TTD == 20
    assert pool.op_start == 8
    assert pool.op_end == 20
    assert pool.op_days == 5
    assert pool.mass_steel == 5000
    assert pool.cp_steel == 460
    assert pool.T_steel_in == 25

def test_zinc_pool_init_custom():
    custom_params = {
        'mass': 100e3,
        'temp_initial': 460,
        'cp_zinc': 500,
        'UA_loss': 600,
        'target_temp': 470,
        'ttd_hx': 15,
        'op_start_hour': 7,
        'op_end_hour': 21,
        'op_days_per_week': 6,
        'mass_steel_per_hour': 4000,
        'cp_steel': 480,
        'T_steel_inlet': 30
    }
    pool = ZincPool(custom_params)
    assert pool.mass == 100e3
    assert pool.temperature == 460
    assert pool.cp == 500
    assert pool.UA == 600
    assert pool.target == 470
    assert pool.TTD == 15
    assert pool.op_start == 7
    assert pool.op_end == 21
    assert pool.op_days == 6
    assert pool.mass_steel == 4000
    assert pool.cp_steel == 480
    assert pool.T_steel_in == 30

def test_zinc_pool_is_operating():
    pool = ZincPool()
    
    # Weekday working hours (Wednesday 10:00)
    ts_work = datetime(2026, 5, 20, 10, 0, 0)
    assert pool.is_operating(ts_work) is True
    
    # Weekday non-working hours (Wednesday 22:00)
    ts_night = datetime(2026, 5, 20, 22, 0, 0)
    assert pool.is_operating(ts_night) is False
    
    # Weekend working hours (Saturday 10:00)
    ts_sat = datetime(2026, 5, 23, 10, 0, 0)
    assert pool.is_operating(ts_sat) is False

def test_zinc_pool_heat_losses():
    pool = ZincPool()
    # T_zinc = 450, T_amb = 20, UA = 500
    # Q_loss = 500 * (450 - 20) / 1000 = 215 kW
    assert abs(pool.heat_loss_kW(20.0) - 215.0) < 1e-6

def test_zinc_pool_heat_to_parts():
    pool = ZincPool()
    
    # Non-operating time: heat to parts should be 0
    ts_night = datetime(2026, 5, 20, 22, 0, 0)
    assert pool.heat_to_parts_kW(ts_night) == 0.0
    
    # Operating time: Wednesday 10:00
    # Q_parts = mass_steel * cp_steel * (T_zinc - T_steel_in) / 3600 / 1000
    #         = 5000 * 460 * (450 - 25) / 3600 / 1000 = 271.5277 kW
    ts_work = datetime(2026, 5, 20, 10, 0, 0)
    expected_q_parts = 5000.0 * 460.0 * (450.0 - 25.0) / 3600.0 / 1000.0
    assert abs(pool.heat_to_parts_kW(ts_work) - expected_q_parts) < 1e-4

def test_zinc_pool_process_outlet_temp():
    pool = ZincPool()
    # T_zinc = 450, TTD = 20
    assert pool.process_outlet_temp() == 470.0

def test_zinc_pool_update():
    pool = ZincPool()
    ts_work = datetime(2026, 5, 20, 10, 0, 0)
    
    # Let's perform a step update
    # mass = 150e3, cp = 512. Thermal inertia (C_vol) = 7.68e7 J/K = 7.68e4 kJ/K
    # dt_s = 3600 (1 hour)
    # T_amb = 20. Q_loss = 215 kW. Q_parts = 271.5278 kW.
    # Total losses + parts = 486.5278 kW
    # If Q_in_kW = 600 kW, net heat = 600 - 486.5278 = 113.4722 kW
    # Net energy = 113.4722 * 3600 kJ = 408500 kJ
    # dT = 408500 / (150e3 * 0.512) = 5.319 C
    # Expected temperature = 450 + 5.319 = 455.319 C
    # Wait, the pool is already at or above target temperature (450 == 450).
    # Since T_zinc >= target, Q_needed = Q_loss + Q_parts + (target - temperature) * mass * cp / (1000 * dt_s)
    # Target = 450, current = 450. So Q_needed = 215 + 271.5278 = 486.5278 kW.
    # Q_used = max(0, min(Q_in_kW, Q_needed)) = max(0, min(600, 486.5278)) = 486.5278 kW.
    # So net_kW = 486.5278 - 215 - 271.5278 = 0.0.
    # Thus, temperature should remain exactly 450.0!
    t_new = pool.update(Q_in_kW=600.0, dt_s=3600.0, T_amb=20.0, timestamp=ts_work)
    assert abs(t_new - 450.0) < 1e-6
    
    # Let's test heating up when temperature is below target
    pool.temperature = 440.0
    # Q_loss = 500 * (440 - 20) / 1000 = 210 kW
    # Q_parts = 5000 * 460 * (440 - 25) / 3600 / 1000 = 265.1389 kW
    # Q_loss + Q_parts = 475.1389 kW
    # Since temperature (440) < target (450), the min/max clamp is bypassed and Q_used = Q_in_kW
    # If Q_in_kW = 600 kW, net_kW = 600 - 475.1389 = 124.8611 kW
    # dT = 124.8611 * 1000 * 3600 / (150e3 * 512) = 5.85286 C
    # Expected temperature = 440 + 5.85286 = 445.85286 C
    expected_q_loss = 500.0 * (440.0 - 20.0) / 1000.0
    expected_q_parts = 5000.0 * 460.0 * (440.0 - 25.0) / 3600.0 / 1000.0
    net_kw = 600.0 - expected_q_loss - expected_q_parts
    expected_dt = net_kw * 1000.0 * 3600.0 / (150e3 * 512.0)
    
    t_new2 = pool.update(Q_in_kW=600.0, dt_s=3600.0, T_amb=20.0, timestamp=ts_work)
    assert abs(t_new2 - (440.0 + expected_dt)) < 1e-6
