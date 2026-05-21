"""
SINGLE SOURCE OF TRUTH — Simulation Parameters
===============================================
Every hardcoded constant and design parameter for the PBTES solar thermal
plant simulation lives here. Import from this module instead of scattering
magic numbers across scripts.

Usage:
    from pbtes.config import baseline_config, SimulationConfig

    tes_params, component_params, conexion_params = baseline_config()
    solver = Solver(tes_params, component_params, conexion_params, HTF='INCOMP::NaK')

Or use the structured config object for parametric sweeps:
    cfg = SimulationConfig()
    cfg.tes.tank_diameter = 8.0
    cfg.solar.aperture_area = 2000.0

All numeric values below are in **SI units** unless explicitly noted (e.g. °C, bar).
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional

# ═══════════════════════════════════════════════════════════════════════
# 1.  TES — Packed Bed Thermal Energy Storage
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TESConfig:
    """Packed bed TES geometry, fill material, and tank construction."""

    # ── Geometry ──────────────────────────────────────────────────────
    tank_height: float = 5.0          # m   — packed bed height
    tank_diameter: float = 7.0        # m   — internal tank diameter
    wall_thickness: float = 0.020     # m   — steel wall thickness
    insulation_thickness: float = 0.750  # m — mineral wool / rockwool

    # ── Fill material (rock / ceramic pebbles) ─────────────────────────
    particle_diameter: float = 0.050  # m   — dp (50 mm = typical rock)
    void_fraction: float = 0.4        # —   — porosity ε
    solid_density: float = 3500.0     # kg/m³  — ρ_s
    solid_specific_heat: float = 968.0  # J/(kg·K) — cp_s
    solid_conductivity: float = 1.6   # W/(m·K) — k_s

    # ── Tank materials ─────────────────────────────────────────────────
    tank_conductivity: float = 45.0   # W/(m·K) — steel wall
    insulation_conductivity: float = 0.03  # W/(m·K) — mineral wool

    # ── Internal computation ───────────────────────────────────────────
    grid_points: int = 20             # spatial nodes along height
    htf_pressure: float = 102325.0    # Pa — HTF operating pressure (~1 atm)
    discharge_tube_diameter: float = 0.0254  # m — 1" tube for discharge
    h_conv_natural: float = 4.0       # W/(m²·K) — natural convection outside tank

    # ── Initial condition ──────────────────────────────────────────────
    initial_temperature: float = 490.0  # °C — uniform initial T profile

    # ── Design-point ranges (parametric sweeps) ────────────────────────
    range_tank_height: Tuple[float, float] = (2.0, 10.0)   # m
    range_tank_diameter: Tuple[float, float] = (3.0, 10.0)  # m
    range_particle_diameter: Tuple[float, float] = (0.02, 0.10)  # m
    range_void_fraction: Tuple[float, float] = (0.30, 0.50)


# ═══════════════════════════════════════════════════════════════════════
# 2.  PTC — Parabolic Trough Collector Field
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PTCConfig:
    """Solar field design-point parameters (sent to TESPy PTC component)."""

    aperture_area: float = 1000.0     # m²   — total aperture area
    optical_efficiency: float = 0.816  # —   — η_opt (clean mirrors)
    aoi: float = 20.0                 # °    — angle of incidence at design
    doc: float = 1.0                  # —   — direct-on-collector flag
    design_irradiance: float = 900.0  # W/m² — design-point DNI
    design_ambient: float = 20.0      # °C   — design-point ambient T

    # ── Thermal loss polynomial: Q_loss = c1·ΔT + c2·ΔT² ──────────────
    c_1: float = 0.0622               # W/(m²·K)
    c_2: float = 0.00023              # W/(m²·K²)

    # ── Incidence angle modifier: IAM = 1 + iam_1·θ + iam_2·θ² ────────
    iam_1: float = -1.59e-3           # 1/°
    iam_2: float =  9.77e-5           # 1/°²

    # ── Global convergence retries ─────────────────────────────────────
    gc_retries: int = 5               # attempts before raising

    # ── Design-point ranges ────────────────────────────────────────────
    range_aperture: Tuple[float, float] = (500.0, 10000.0)  # m²
    range_eta_opt: Tuple[float, float] = (0.65, 0.85)


# ═══════════════════════════════════════════════════════════════════════
# 3.  PROCESS — Industrial heat demand
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ProcessConfig:
    """Process heat exchanger setpoints (galvanizing plant)."""

    # ── Heat demand ────────────────────────────────────────────────────
    heat_demand: float = -450000.0    # W — negative = heat removed from loop

    # ── Temperature setpoints (connection labels match TESPy numbering) ─
    T_5: float = 520.0   # °C — preheater outlet / process HX inlet
    T_6: float = 480.0   # °C — process HX outlet (return)

    # ── Pressure setpoints ─────────────────────────────────────────────
    p_6: float = 50.0                 # bar — process loop pressure
    p_13: float = 5.0                 # bar — TES charge secondary loop
    p_15: float = 5.0                 # bar — TES discharge secondary loop

    # ── Component efficiencies ─────────────────────────────────────────
    pump_isentropic_efficiency: float = 0.85  # —
    compressor_isentropic_efficiency: float = 0.80  # —

    # ── HX pressure drops (pr = p_out / p_in) ──────────────────────────
    pr_ptc: float = 1.0               # PTC pressure ratio
    pr_process_hx: float = 1.0        # process HX pressure ratio
    pr_preheater: float = 1.0         # preheater/aux HX pressure ratio
    pr_charge_hx: float = 0.98        # charge TES HX (hot side)
    pr_charge_hx_cold: float = 0.98   # charge TES HX (cold side)
    pr_discharge_hx: float = 0.98     # discharge TES HX

    # ── HX terminal temperature difference ─────────────────────────────
    ttd_charge_hx: float = 20.0       # K — design TTD for charge HX
    ttd_discharge_hx: float = 20.0    # K — design TTD for discharge HX

    # ── Pump fallback (used when pump component missing from network) ─
    pump_fallback_density: float = 1850.0    # kg/m³
    pump_fallback_delta_p: float = 500000.0  # Pa — 5 bar
    pump_fallback_efficiency: float = 0.75   # —


# ═══════════════════════════════════════════════════════════════════════
# 4.  HTF — Heat Transfer Fluids
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class HTFConfig:
    """Fluid selection and operating envelopes."""

    # ── Primary HTF (PTC loop) ─────────────────────────────────────────
    htf: str = 'INCOMP::NaK'          # CoolProp fluid string
    htf_tes: str = 'INCOMP::NaK'      # TES secondary loop fluid

    # ── Temperature limits ─────────────────────────────────────────────
    T_min: float = 300.0              # °C — minimum valid temp (CoolProp / physics)
    T_max: float = 600.0              # °C — maximum valid temp (NaK safe limit)
    T_min_clamp: float = 300.1        # °C — numerical clamp in packed_bed

    # ── Allowed alternative fluids ─────────────────────────────────────
    alternatives: List[str] = field(default_factory=lambda: [
        'INCOMP::NaK',
        'INCOMP::SolarSalt',
        'CO2',
        'Water',
        'Air',
    ])

    # ── Fluid-specific design pressures (for alternatives) ────────────
    fluid_pressure_map: Dict[str, List[float]] = field(default_factory=lambda: {
        'INCOMP::NaK': [5.0, 5.0],
        'INCOMP::SolarSalt': [5.0, 5.0],
        'CO2': [50.0, 5.0],
        'Water': [5.0, 5.0],
        'Air': [5.0, 5.0],
    })


# ═══════════════════════════════════════════════════════════════════════
# 5.  ZINC — Galvanizing zinc pool process model
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ZincConfig:
    """Lumped-capacitance model of the galvanizing zinc bath."""

    # ── Zinc bath ──────────────────────────────────────────────────────
    mass: float = 150000.0            # kg — zinc mass in bath (150 tonnes)
    temperature_initial: float = 450.0  # °C
    target_temperature: float = 450.0   # °C
    cp_zinc: float = 512.0            # J/(kg·K) — molten zinc specific heat
    UA_loss: float = 500.0            # W/K — heat loss coefficient to ambient
    ttd_hx: float = 20.0              # K  — approach ΔT for process HX

    # ── Production schedule ────────────────────────────────────────────
    op_start_hour: int = 8            # 8 am
    op_end_hour: int = 20             # 8 pm
    op_days_per_week: int = 5         # Mon–Fri

    # ── Steel throughput ───────────────────────────────────────────────
    mass_steel_per_hour: float = 5000.0  # kg/h — steel processed
    cp_steel: float = 460.0           # J/(kg·K)
    T_steel_inlet: float = 25.0       # °C — parts entering bath at ambient


# ═══════════════════════════════════════════════════════════════════════
# 6.  SOLVER — Convergence, control, and time-stepping
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SolverConfig:
    """Orchestration parameters for the quasi-steady simulation."""
    base_design_dir: str = '.tespy_cache'  # Cache directory for design states

    # ── Time ───────────────────────────────────────────────────────────
    time_step: float = 3600.0         # s — 1-hour time step
    time_step_hours: float = 1.0      # h — same, in hours

    # ── Simulation control ─────────────────────────────────────────────
    fixed_year: int = 2022            # year assigned to TMY data
    system_mode: str = 'Full'         # 'Full' | 'NoTES'
    topology: str = 'Parallel'        # 'Parallel' | 'Series'
    tank_config: str = 'indirect'     # 'indirect' | 'direct'
    charge_margin: float = 1.5        # —  multiplier on E_min_process for charge

    # ── Convergence ────────────────────────────────────────────────────
    tes_coupling_max_iter: int = 20       # max iterations per time-step
    attempt_to_solve_tries: int = 5       # attempts per mode solve
    attempt_to_solve_tries_mode5: int = 10
    design_max_iter: int = 100            # network solve (design mode)
    offdesign_max_iter: int = 200         # network solve (offdesign mode)

    # ── Convergence diagnostics ────────────────────────────────────────
    conv_window: int = 3              # samples for convergence check
    conv_threshold: float = 0.05      # relative T_out change < 5% = converged
    div_window: int = 5               # samples for divergence check
    div_threshold: float = 1.0        # > 100% increase = diverging

    # ── Mode dwell ─────────────────────────────────────────────────────
    mode_dwell_min_steps: int = 2     # minimum steps before changing mode

    # ── Connection initial guesses (T0) by mode ────────────────────────
    guess_T0_mode_1: float = 500.0    # °C
    guess_T0_mode_2: float = 500.0    # °C
    guess_T0_mode_3: float = 520.0    # °C
    guess_T0_mode_4: float = 500.0    # °C
    guess_T0_mode_5: float = 550.0    # °C
    guess_T0_mode_6: float = 500.0    # °C

    guess_h0: float = 700.0           # kJ/kg
    guess_m0: float = 5.0             # kg/s (Parallel), 2 kg/s (Series)
    guess_p0: float = 5.0             # bar

    # ── Retry randomization bounds ─────────────────────────────────────
    retry_T_bounds: List[Tuple[float, float]] = field(default_factory=lambda: [
        (350.0, 550.0),
        (300.0, 600.0),
        (250.0, 650.0),
        (200.0, 700.0),
    ])
    retry_m_bounds: Tuple[float, float] = (20.0, 50.0)    # kg/s
    retry_p_bounds: Tuple[float, float] = (1.0, 10.0)     # bar
    retry_h_bounds: Tuple[float, float] = (500.0, 1000.0)  # kJ/kg

    # ── Mode-selection thresholds ──────────────────────────────────────
    T_max_discharge: float = 580.0    # °C — NaK safe limit −20 K
    soc_empty_ref: float = 400.0      # °C — uniform profile for SoC=0 reference
    soc_full_ref: float = 560.0       # °C — uniform profile for SoC=1 reference

    soc_mode6_sticky: float = 0.80    # stay in Mode 6 if soc_norm below this
    soc_mode4_threshold: float = 0.05  # below this → standby (Mode 4) if no sun
    soc_mode6_cold: float = 0.40      # below this + TES_top < 470 → Mode 6
    T_mode6_cold_top: float = 470.0   # °C — TES_top threshold for cold-Mode6
    soc_mode5_high: float = 0.90      # above this → Mode 5 (high-T charge)
    soc_mode1_threshold: float = 0.99  # below this → Mode 1 viable
    soc_mode3_minimum: float = 0.10   # above this → Mode 3 viable (discharge)
    irr_mode2_no_tes: float = 300.0   # W/m² — threshold for Mode 2 (>300)

    # ── Mass flow alert ────────────────────────────────────────────────
    min_mass_flow_alert: float = 0.01  # kg/s

    # ── Design-point initialization irradiance by mode ─────────────────
    init_irr_mode_1: float = 1000.0   # W/m²
    init_irr_mode_2: float = 1000.0
    init_irr_mode_3: float = 0.0
    init_irr_mode_4: float = 0.0
    init_irr_mode_5: float = 1000.0
    init_irr_mode_6: float = 1000.0

    # ── Design-point initial TES temperature by mode ───────────────────
    init_T_tes_mode_1: float = 400.0  # °C
    init_T_tes_mode_2: float = 520.0  # °C
    init_T_tes_mode_3: float = 540.0  # °C
    init_T_tes_mode_4: float = 450.0  # °C
    init_T_tes_mode_5: float = 400.0  # °C
    init_T_tes_mode_6: float = 400.0  # °C

    # ── Connection T overrides (design) ─────────────────────────────────
    conn_15_T_mode_3: float = 540.0   # °C
    conn_13_T_mode_5: float = 400.0   # °C
    conn_13_T_mode_6: float = 400.0   # °C


# ═══════════════════════════════════════════════════════════════════════
# 7.  ECONOMICS — Levelized Cost of Heat
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class EconomicsConfig:
    """LCOH calculation parameters."""

    discount_rate: float = 0.08       # 8%
    lifetime: int = 25                # years
    base_capex: float = 1_000_000.0   # USD — solar field, piping, controls, etc.
    tank_cost_per_m3: float = 500.0   # USD/m³
    htf_cost_per_kg: float = 2.0      # USD/kg
    opex_fraction: float = 0.02       # 2% of CAPEX per year
    htf_density_for_mass: float = 1900.0  # kg/m³ (for HTF mass from tank volume)
    
    # ── Operational Cost Assumptions ───────────────────────────────────
    electricity_price_per_kwh: float = 0.10  # USD/kWh
    aux_fuel_price_per_kwh: float = 0.05     # USD/kWh (equivalent thermal)
    om_rate_fraction: float = 0.02           # 2% of total equipment CAPEX per year for O&M



# ═══════════════════════════════════════════════════════════════════════
# 8.  HEAT TRANSFER CORRELATIONS — packed bed (numerical constants)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class HeatTransferConfig:
    """
    Dimensionless correlation constants inside the packed bed.
    These should NOT be changed without a strong physical justification.
    """

    # ── Volumetric HTC: hv = ff * (k_f/dp) * C_v * Re^n_v * Pr^(1/3) ──
    hv_prefactor: float = 1.32
    hv_re_exponent: float = 0.59
    hv_pr_exponent: float = 1.0 / 3.0

    # ── Internal particle HTC: hint = (k_f/dp) * (C_i1·Re^⅓·Pr^⅓ + C_i2·Re^0.8·Pr^0.4) ─
    hint_prefactor_1: float = 0.203
    hint_prefactor_2: float = 0.22
    hint_re_exponent_1: float = 1.0 / 3.0
    hint_re_exponent_2: float = 0.8
    hint_pr_exponent_1: float = 1.0 / 3.0
    hint_pr_exponent_2: float = 0.4

    # ── Stanton multiplier ─────────────────────────────────────────────
    stanton_multiplier: float = 0.75

    # ── Shape factor: ff = 6 * (1 - ε) / dp ────────────────────────────
    shape_factor_coefficient: float = 6.0

    # ── Numerical stability ────────────────────────────────────────────
    a_clip_value: float = 15.0        # clip |a| to avoid sinh/cosh overflow
    root_margin: float = 1e-5         # epsilon for Brent root-finding bracket
    num_eigenvalues: int = 200        # number of eigenvalues computed
    num_integration_points: int = 200  # for integral in analytical solution


# ═══════════════════════════════════════════════════════════════════════
# 9.  REPORTING & OUTPUT
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ReportingConfig:
    """Figure sizes, output paths, and format settings."""

    # ── Figure sizes (inches) ──────────────────────────────────────────
    figsize_default: Tuple[float, float] = (8.0, 5.0)
    figsize_wide: Tuple[float, float] = (10.0, 4.6)
    figsize_large: Tuple[float, float] = (11.0, 9.0)
    figsize_square: Tuple[float, float] = (7.0, 5.5)
    figsize_half: Tuple[float, float] = (10.0, 4.5)

    # ── Matplotlib rcParams ───────────────────────────────────────────
    font_family: str = 'serif'
    font_size: float = 11.0
    dpi: int = 300

    # ── Output directories ─────────────────────────────────────────────
    out_dir_baseline: str = 'article_results/01_baseline/'
    out_dir_parametric: str = 'article_results/02_parametric/'
    out_dir_analysis: str = 'article_results/05_analysis/'
    out_dir_figures: str = 'article_results/06_figures/'
    out_dir_synthesis: str = 'article_results/07_synthesis/'

    # ── Energy unit conversions ────────────────────────────────────────
    kJ_to_MWh: float = 3.6e6          # kJ → MWh
    kJ_to_GWh: float = 3.6e9          # kJ → GWh
    J_to_kWh: float = 3.6e6           # J → kWh (for SoC)

    # ── CSV column headings (for output compatibility) ─────────────────
    weather_file: str = 'TMY.csv'


# ═══════════════════════════════════════════════════════════════════════
# 10. TOP-LEVEL — Complete simulation configuration
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SimulationConfig:
    """Aggregates all sub-system configurations."""
    tes: TESConfig = field(default_factory=TESConfig)
    ptc: PTCConfig = field(default_factory=PTCConfig)
    process: ProcessConfig = field(default_factory=ProcessConfig)
    htf: HTFConfig = field(default_factory=HTFConfig)
    zinc: ZincConfig = field(default_factory=ZincConfig)
    solver: SolverConfig = field(default_factory=SolverConfig)
    economics: EconomicsConfig = field(default_factory=EconomicsConfig)
    heat_transfer: HeatTransferConfig = field(default_factory=HeatTransferConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)


# ═══════════════════════════════════════════════════════════════════════
# 11. BACKWARD-COMPATIBLE FACTORY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def baseline_config():
    """
    Return the three dicts expected by Solver.__init__ for the
    canonical baseline design (Parallel topology, NaK HTF, indirect tank).

    Returns
    -------
    tes_params : dict
        TES geometry, material, and initial condition.
    component_params : dict
        PTC field, process HX, pump efficiencies.
    conexion_params : dict
        Connection temperature/pressure setpoints and fluid composition.

    Example
    -------
    >>> tes_p, comp_p, conn_p = baseline_config()
    >>> solver = Solver(tes_p, comp_p, conn_p, HTF='INCOMP::NaK')
    """
    c = SimulationConfig()

    tes_params = {
        'HTF': c.htf.htf_tes,
        'Initial temperature': c.tes.initial_temperature,
        'Tank length': c.tes.tank_height,
        'Particle diameter': c.tes.particle_diameter,
        'Tank diameter': c.tes.tank_diameter,
        'Void fraction': c.tes.void_fraction,
        'Solid density': c.tes.solid_density,
        'Solid specific heat': c.tes.solid_specific_heat,
        'Solid conductivity': c.tes.solid_conductivity,
        'Wall thickness': c.tes.wall_thickness,
        'Tank conductivity': c.tes.tank_conductivity,
        'Insulation thickness': c.tes.insulation_thickness,
        'Insulation conductivity': c.tes.insulation_conductivity,
    }

    component_params = {
        'pump_eta_s': c.process.pump_isentropic_efficiency,
        'comp_eta_s': c.process.compressor_isentropic_efficiency,
        'ptc_pr': c.process.pr_ptc,
        'ptc_aoi': c.ptc.aoi,
        'ptc_doc': c.ptc.doc,
        'ptc_tamb': c.ptc.design_ambient,
        'ptc_A': c.ptc.aperture_area,
        'eta_opt': c.ptc.optical_efficiency,
        'ptc_c_1': c.ptc.c_1,
        'ptc_c_2': c.ptc.c_2,
        'ptc_E': c.ptc.design_irradiance,
        'ptc_iam_1': c.ptc.iam_1,
        'ptc_iam_2': c.ptc.iam_2,
        'PR_pr': c.process.pr_process_hx,
        'PR_Q': c.process.heat_demand,
        'PH_pr': c.process.pr_preheater,
    }

    conexion_params = {
        '5_T': c.process.T_5,
        '6_T': c.process.T_6,
        '6_p': c.process.p_6,
        '6_f': {c.htf.htf: 1},
        '13_p': c.process.p_13,
        '13_f': {c.htf.htf_tes: 1},
        '15_p': c.process.p_15,
        '15_f': {c.htf.htf_tes: 1},
    }

    return tes_params, component_params, conexion_params


def zinc_pool_config():
    """
    Return the zinc pool params dict expected by ZincPool.__init__.
    """
    c = SimulationConfig()
    return {
        'mass': c.zinc.mass,
        'temp_initial': c.zinc.temperature_initial,
        'cp_zinc': c.zinc.cp_zinc,
        'UA_loss': c.zinc.UA_loss,
        'target_temp': c.zinc.target_temperature,
        'ttd_hx': c.zinc.ttd_hx,
        'op_start_hour': c.zinc.op_start_hour,
        'op_end_hour': c.zinc.op_end_hour,
        'op_days_per_week': c.zinc.op_days_per_week,
        'mass_steel_per_hour': c.zinc.mass_steel_per_hour,
        'cp_steel': c.zinc.cp_steel,
        'T_steel_inlet': c.zinc.T_steel_inlet,
    }


# ═══════════════════════════════════════════════════════════════════════
# 12. MODE REFERENCE TABLE
# ═══════════════════════════════════════════════════════════════════════

MODE_TABLE = {
    '1': 'Solar charges TES + serves process',
    '2': 'Solar to process only (TES standby)',
    '3': 'TES discharge to process only (no sun)',
    '4': 'Standby — auxiliary heater serves process',
    '5': 'High-T solar charges TES + serves process (Parallel only)',
    '6': 'Solar charges TES + process decoupled (Parallel only)',
}

# For each mode: whether PTC runs, TES charges, TES discharges, Aux runs
MODE_INTERACTIONS = {
    '1': {'PTC': True,  'TES_charge': True,  'TES_discharge': False, 'Aux': False},
    '2': {'PTC': True,  'TES_charge': False, 'TES_discharge': False, 'Aux': False},
    '3': {'PTC': False, 'TES_charge': False, 'TES_discharge': True,  'Aux': False},
    '4': {'PTC': False, 'TES_charge': False, 'TES_discharge': False, 'Aux': True},
    '5': {'PTC': True,  'TES_charge': True,  'TES_discharge': False, 'Aux': True},
    '6': {'PTC': True,  'TES_charge': True,  'TES_discharge': False, 'Aux': True},
}
