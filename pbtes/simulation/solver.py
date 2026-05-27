import numpy as np
import pandas as pd
import time, os, json
from copy import deepcopy
from tqdm import tqdm
import CoolProp.CoolProp as cp
import tespy.networks as tpn
import tespy.connections as tpcn
import tespy.components as tpc

from pbtes.storage import ThermalEnergyStorage, ZincPool
from pbtes.network.system import SolarThermalSystem


class Solver:
    """
    Runs a quasi-steady simulation of the SolarThermalSystem over time-series data.
    """
    def __init__(self, 
                 tes_params,
                 component_params,
                 conexion_params,
                 HTF,
                 system_mode='Full', 
                 topology='Parallel',
                 tank_config='indirect',
                 file_path=None,
                 charge_margin=1.5,
                 zinc_pool_params=None):
        self.tes_params= tes_params
        self.component_params = component_params
        self.conexion_params = conexion_params
        self.HTF= HTF 
        self.system_mode = system_mode
        self.topology = topology
        self.tank_config = tank_config  # 'direct' or 'indirect'
        self.results = []
        self.current_mode = '4' 
        self.file_path = file_path
        self.mode_alert = False
        
        # --- Control parameters (visible for parametric analysis) ---
        A_ptc   = self.component_params.get('ptc_A', 10000)
        eta_opt = self.component_params.get('eta_opt', 0.75)
        Q_proc  = abs(self.component_params.get('PR_Q', 1e6))
        E_design = self.component_params.get('ptc_E', 900)
        self.E_min_process = Q_proc / (A_ptc * eta_opt)  # W/m2 — minimum to serve process
        self.E_min_charge  = self.E_min_process * charge_margin
        self.charge_margin = charge_margin
        # Mode 1 fires when solar can serve process AND charge TES with meaningful surplus.
        # Needs ~10% margin above E_min_charge for reliable offdesign convergence
        # (LMTD singularity at low heat loads). Also floor at 600 W/m2 for kA stability.
        self.E_min_mode1   = max(self.E_min_charge * 1.1, 600.0)
        # ---
        
        # --- Zinc pool (optional dynamic process model) ---
        self.zinc_pool = ZincPool(zinc_pool_params) if zinc_pool_params is not None else None
        # ---

        print(f'Control thresholds: E_min_process={self.E_min_process:.0f} W/m2, '
              f'E_min_charge={self.E_min_charge:.0f} W/m2, '
              f'E_min_mode1={self.E_min_mode1:.0f} W/m2 '
              f'(A_ptc={A_ptc} m2, eta_opt={eta_opt}, Q_proc={Q_proc/1e6:.3f} MW, '
              f'E_design={E_design} W/m2, margin={charge_margin}x)')

    def load_data(self, csv, start_date, days_to_simulate):
        """
        Loads external data from a CSV file and fixes the year for all timestamps.
        :return: DataFrame, data loaded and adjusted.
        """
        fixed_year = 2022        

        # 2) Read TMY
        tmy_data = pd.read_csv(csv)#, parse_dates=['Fecha/Hora'])
        
        # Fix the year for all timestamps
        tmy_data['Fecha/Hora'] = pd.to_datetime(tmy_data['Fecha/Hora'])
        tmy_data['Fecha/Hora'] = tmy_data['Fecha/Hora'].apply(lambda x: x.replace(year=fixed_year))
        start_date = tmy_data['Fecha/Hora'].min()
        end_date   = start_date + pd.Timedelta(days=days_to_simulate)
        print(start_date, end_date)
       
        #filtered_data = filtered_data[filtered_data['Fecha/Hora'] >= start_date]
        filtered_data = tmy_data[(tmy_data['Fecha/Hora'] >= start_date) & (tmy_data['Fecha/Hora'] < end_date)]
        return filtered_data


    def get_mode(self, irr, TES_profile, prev_TES_lay):
        """
        Seleccion de modo basado en irradiancia, SOC, y viabilidad fisica.
        
        Thresholds (set in Solver.__init__):
          self.E_min_process : irradiancia minima para que el PTC entregue Q_proc
          self.E_min_charge  : irradiancia minima para cargar TES (process + margen)
          self.charge_margin : multiplicador para E_min_charge
        """
    
        # --- Top/Bottom coherentes con el layout previo ---
        lay = prev_TES_lay or getattr(self, 'TES_lay', 'Charge')
        if lay == 'Charge':
            TES_top = TES_profile[0];  TES_bot = TES_profile[-1]
        else:  # 'Discharge'
            TES_top = TES_profile[-1]; TES_bot = TES_profile[0]
            
        t_proc_set = self.solar_system.conexion_params['6_T']
        t_ph_out   = self.solar_system.conexion_params['5_T']
        
        # Discharge viability thresholds (adaptive to process temperatures)
        T_min_discharge = t_proc_set + 20  # 480+20=500 C (T04 = T15-20 >= T11 = 480)
        T_max_discharge = 580              # NaK safe limit - 20, expanded range
        
        # Calculate State of Charge (SOC)
        is_series_direct = (self.tank_config == 'direct' and self.topology == 'Series'
                            and hasattr(self.solar_system, 'cold_tes'))
        if is_series_direct:
            hot_soc = self.solar_system.hot_tes.calculate_SoC(
                self.solar_system.hot_tes.profile)
            cold_soc = self.solar_system.cold_tes.calculate_SoC(
                self.solar_system.cold_tes.profile)
            current_soc = hot_soc + cold_soc
            soc_empty_h = self.solar_system.hot_tes.calculate_SoC(
                np.ones_like(self.solar_system.hot_tes.profile) * 400.0)
            soc_full_h = self.solar_system.hot_tes.calculate_SoC(
                np.ones_like(self.solar_system.hot_tes.profile) * 560.0)
            soc_empty_c = self.solar_system.cold_tes.calculate_SoC(
                np.ones_like(self.solar_system.cold_tes.profile) * 400.0)
            soc_full_c = self.solar_system.cold_tes.calculate_SoC(
                np.ones_like(self.solar_system.cold_tes.profile) * 560.0)
            soc_norm = ((current_soc - soc_empty_h - soc_empty_c)
                        / max(soc_full_h + soc_full_c - soc_empty_h - soc_empty_c, 1e-3))
        else:
            current_soc = self.solar_system.tes.calculate_SoC(TES_profile)
            soc_empty = self.solar_system.tes.calculate_SoC(np.ones_like(TES_profile) * 400.0)
            soc_full = self.solar_system.tes.calculate_SoC(np.ones_like(TES_profile) * 560.0)
            soc_norm = (current_soc - soc_empty) / max(soc_full - soc_empty, 1e-3)
    
        # --- Lectura interna (opcional) de T_ptc_out desde la red actual ---
        def _read_T_ptc_out():
            for cname in ('conn_02', 'conn_04'):
                c = getattr(self.solar_system, cname, None)
                if c is not None and hasattr(c, 'T') and c.T is not None:
                    try:
                        if getattr(c.T, 'val', None) is not None:
                            return float(c.T.val)
                        if getattr(c.T, 'val_SI', None) is not None:
                            return float(c.T.val_SI - 273.15)
                    except AttributeError:
                        pass
            return None
    
        T_ptc_out = _read_T_ptc_out()
    
        # --- Dwell: mantener modo previo por 2 pasos para evitar oscilaciones ---
        if hasattr(self, '_mode_dwell') and self._mode_dwell < 2:
            self._mode_dwell += 1
            return self.prev_TESmode

        # --- Pegajosidad: permanecer en Mode 6 si TES aun necesita carga ---
        if self.prev_TESmode == '6' and soc_norm < 0.8 and irr > self.E_min_process:
            return '6'
    
        # --- TES muy frio y poca irradiancia -> standby ---
        if soc_norm < 0.05 and irr < self.E_min_process:
            return '4'
    
        # --- TES frio moderado: cargar TES si hay irradiancia suficiente ---
        if soc_norm < 0.4 and TES_top < 470:
            return '6' if irr > self.E_min_charge else '4'
    
        # --- Irradiancia suficiente para proceso + carga ---
        if irr > self.E_min_charge:
            # Mode 5: high-T charge when tank is warm and irradiance is sufficient
            if TES_top > t_ph_out and soc_norm < 0.90:
                return '5'
            # Mode 1: charge TES + serve process — only when irradiance is high enough
            # for the charge HX to operate well above its design minimum (avoids kA
            # ill-conditioning when the available surplus heat is too small).
            charge_viable = True
            if T_ptc_out is not None:
                charge_viable = (T_ptc_out > TES_top)
            # Add thermodynamic check for indirect charging temperature difference
            if self.tank_config == 'indirect':
                TES_bot = TES_profile[-1] if prev_TES_lay == 'Charge' else TES_profile[0]
                # Thermodynamic limit: cold outlet (TES_bot + 40) must be lower than hot inlet (500°C) minus pinch (20K)
                if TES_bot > 440.0:
                    charge_viable = False
            if irr >= self.E_min_mode1 and charge_viable and soc_norm < 0.99:
                return '1'
            else:
                return '2'
    
        # --- Irradiancia suficiente solo para proceso (sin excedente para carga) ---
        if irr > self.E_min_process:
            # Check discharge first: if TES has energy, use it + top up with PTC
            if TES_top > T_min_discharge and TES_top <= T_max_discharge and soc_norm > 0.1:
                return '3'
            return '2'
    
        # --- Baja irradiancia: descargar TES si tiene energia ---
        if TES_top > T_min_discharge and TES_top <= T_max_discharge and soc_norm > 0.1:
            return '3'
        return '4'
    

    def get_system_mode(self, irr):
        if self.system_mode == 'Full':
            new_TESmode = self.get_mode(irr, self.solar_system.tes.profile, self.TES_lay)
            # Reset dwell counter when mode actually changes
            if new_TESmode != self.prev_TESmode:
                self._mode_dwell = 0
            self.prev_TESmode = new_TESmode
        elif self.system_mode == 'No TES':
            if irr > 300:
                new_TESmode = '2'
            else:
                new_TESmode = '4'
        elif self.system_mode == 'No solar':
            new_TESmode = '4'
        return new_TESmode
    def init_steady(self, irr, mode='design'):
        self.system_mode = 'Full'
        self.TES_lay = 'Charge'
        self.irr = irr
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF,
                                    topology=self.topology,
                                    tank_config=self.tank_config
                                    )
        print(f"Mode: {mode}")
        self.solve_network_steady(mode=mode)
        self.solar_system.network.print_results()
        
    def initialize_modes(self):
        import os, shutil, glob
        base_dir = '.tespy_cache'
        if os.path.exists(base_dir):
            for f in glob.glob(os.path.join(base_dir, 'base_design_*')):
                if os.path.isfile(f):
                    os.remove(f)
                else:
                    shutil.rmtree(f, ignore_errors=True)
        for f in glob.glob('base_design_*'):
            if os.path.isfile(f):
                os.remove(f)
            else:
                shutil.rmtree(f, ignore_errors=True)

        def _make_system(T_init):
            self.tes_params['Initial temperature'] = T_init
            return SolarThermalSystem(rows=1, tes_params=self.tes_params,
                        component_params=self.component_params,
                        conexion_params=self.conexion_params,
                        HTF=self.HTF, topology=self.topology, tank_config=self.tank_config)
        
        # ---- Mode 1 (charge + process, computes kA) ----
        self.system_mode = 'Full'; self.TES_lay = 'Charge'; self.irr = 1000
        is_series_direct = (self.tank_config == 'direct' and self.topology == 'Series')
        sys1 = _make_system(450)  # Design at warmer T_bot for better offdesign CHX DT
        if is_series_direct:
            sys1.hot_tes.profile = np.ones(20) * 520.0
            sys1.cold_tes.profile = np.ones(20) * 440.0
        self.solar_system = sys1
        self.solve_network_steady(TESmode='1')
        # Store kA for cross-mode use (indirect only) and design TES charge flow for offdesign constraints
        self.charge_hx_kA = getattr(sys1, 'charge_hx_kA', None)
        if not is_series_direct:
            try:
                self.charge_tes_m_design = sys1.conn_13.m.val
            except Exception:
                self.charge_tes_m_design = None
        else:
            self.charge_tes_m_design = None
        ka_str = f"{self.charge_hx_kA:.1f}" if self.charge_hx_kA is not None else "None"
        m_str = f"{self.charge_tes_m_design:.2f}" if self.charge_tes_m_design is not None else "None"
        print(f'[Mode 1 design] kA={ka_str}, m_TES={m_str} kg/s')
        
        # ---- Mode 2 (process only) ----
        self.irr = 1000
        self.solar_system = _make_system(520)
        self.solve_network_steady(TESmode='2')
        
        # ---- Mode 3 (discharge) ----
        self.irr = 0
        sys3 = _make_system(540)
        # Set design TES discharge flow (same order of magnitude as charge)
        if self.charge_tes_m_design is not None:
            sys3.tes_charge_m = self.charge_tes_m_design
        sys3.set_operation_mode(TESmode='3', current_irr=0,
            profile=sys3.tes.profile, prev_TES_lay='Charge', mode='design')
        # conn_15.T is set inside set_operation_mode from TES profile, but override for robustness
        if hasattr(sys3, 'conn_15'):
            sys3.conn_15.set_attr(T=540)
        sys3.solve_network(mode='design', TESmode='3')
        self.solar_system = sys3
        try:
            if hasattr(sys3, 'conn_15'):
                self.discharge_tes_m_design = sys3.conn_15.m.val
            else:
                self.discharge_tes_m_design = self.charge_tes_m_design
        except Exception:
            self.discharge_tes_m_design = self.charge_tes_m_design
        
        # ---- Mode 4 (standby) ----
        self.irr = 0
        self.solar_system = _make_system(450)
        self.solve_network_steady(TESmode='4')
        
        # ---- Mode 5 (high-T charge, retry for convergence) ----
        self.irr = 900
        sys5 = _make_system(400)
        if self.charge_tes_m_design is not None:
            sys5.tes_charge_m = self.charge_tes_m_design
        sys5.set_operation_mode(TESmode='5', current_irr=900,
            profile=sys5.tes.profile, prev_TES_lay='Charge', mode='design')
        self.current_irr = 900
        # Warm-start from Mode 1 design (similar PTC→Charge HX topology)
        ok5, _, _ = self.attempt_to_solve(sys5, 'design', 'base_design', '5', tries=10)
        if ok5 and sys5.network.converged:
            sys5.network.save(os.path.join('.tespy_cache', 'base_design_5'))
        self.solar_system = sys5
        
        # ---- Mode 6 (full TES charge cycle, Parallel: PTC→TES + aux→process) ----
        self.mode6_design_available = False
        try:
            self.irr = 1000
            sys6 = _make_system(400)
            if self.charge_hx_kA:
                sys6.charge_hx_kA = self.charge_hx_kA
            sys6.set_operation_mode(TESmode='6', current_irr=1000,
                profile=sys6.tes.profile, prev_TES_lay='Charge', mode='design')
            if hasattr(sys6, 'conn_13'):
                sys6.conn_13.set_attr(T=400)
            sys6.solve_network(mode='design', TESmode='6')  # saves to .tespy_cache/base_design_6
            if sys6.network.converged:
                self.mode6_design_available = True
                print('[Mode 6 design] Converged — base_design_6 saved.')
            self.solar_system = sys6
        except Exception as e:
            print(f'[WARNING] Mode 6 design initialization failed: {e}')
            print('          Mode 6 offdesign will cold-start (no init_path).')
            # Do NOT copy base_design_4 here — the Mode 4 CSV has incompatible
            # connection labels (no 01_CC_PTC) and causes TESPy "not found" errors.
        

    # -------------------------------------------------------------------------
    # 1) Convergence Checking
    # -------------------------------------------------------------------------
    def _check_tes_convergence(self, T_out_history, conv_factors):
        """
        Checks for two criteria:
          1) Convergence if last 3 changes in T_out are < 5%.
          2) Divergence if the convergence factor has increased >10% 
             over the last 5 iterations.

        Returns
        -------
        str:
            'converged', 'diverged', or 'continue'
        """
        # (1) If we have at least 3 T_out values, check for <5% changes
        if len(T_out_history) >= 3:
            Tn   = T_out_history[-1]
            Tn_1 = T_out_history[-2]
            Tn_2 = T_out_history[-3]

            diff1 = abs(Tn   - Tn_1) / max(abs(Tn_1), 1e-6)
            diff2 = abs(Tn_1 - Tn_2) / max(abs(Tn_2), 1e-6)
            if diff1 < 0.05 and diff2 < 0.05:
                return 'converged'

        # (2) If we have at least 5 convergence factors, check for divergence
        if len(conv_factors) >= 5:
            earliest = conv_factors[-5]
            latest   = conv_factors[-1]
            if earliest > 0 and (latest - earliest)/earliest > 1:
                return 'diverged'

        return 'continue'
    
    def iteration_check(self, TESmode, system):
        if TESmode == '1':
            T_tes_out = system.conn_10.T.val
            if T_tes_out > self.conexion_params['5_T']:
                check = False
                mode = '2'
                #print('T TES out: ', T_tes_out)
            else:
                check = True
                mode = '1'
        elif TESmode == '3':   
            T_tes_out = system.conn_04.T.val
            if T_tes_out < self.conexion_params['6_T']:
                check = False
                mode = '4'
            else:
                check = True
                mode = '3'
        else:
            check = True
            mode = TESmode
        return check, mode
    # -------------------------------------------------------------------------
    # 2) Coupling Iteration Between TES and Main Loop (steady or single time-step)
    # -------------------------------------------------------------------------
    def attempt_to_solve(self, system, mode, design_path, TESmode, tries: int = 5):
        """
        Intenta resolver la red TESPy hasta `tries` veces.
        Implementa estrategias dinÃ¡micas de relajaciÃ³n (fallbacks) 
        para lograr convergencia antes de fallar por completo.
        Devuelve:
          ok: bool                -> True si alguna corrida converge
          attempts: list[dict]    -> bitÃ¡cora por intento
          last_err: str|None      -> mensaje del Ãºltimo error capturado (si hubo)
        """
        attempts = []
        last_err = None
        for k in range(1, tries + 1):
            if k > 1:
                # Recreate network to clear corrupted state from failed solves
                try:
                    saved_profile = (np.array(system.tes.profile).copy()
                        if hasattr(system, 'tes') and system.tes.profile is not None else None)
                    system.set_operation_mode(TESmode=TESmode, mode=mode,
                        current_irr=self.current_irr, profile=saved_profile)
                    # Re-apply TES boundary conditions!
                    tank_cfg = getattr(system, 'tank_config', 'indirect')
                    topo = getattr(system, 'topology', 'Parallel')
                    is_sd_m1 = (TESmode == '1' and tank_cfg == 'direct' and topo == 'Series')
                    if is_sd_m1:
                        system.conn_ht_ph.set_attr(T=system.hot_tes.profile[-1])
                        system.conn_10.set_attr(T=system.cold_tes.profile[-1])
                    elif TESmode in ['1','5','6']:
                        if getattr(self, 'tank_config', 'indirect') == 'direct':
                            system.conn_10.set_attr(T=system.tes.profile[-1])
                        else:
                            system.conn_13.set_attr(T=system.tes.profile[-1])
                    elif TESmode in ['3']:
                        if getattr(self, 'tank_config', 'indirect') == 'direct':
                            system.conn_04.set_attr(T=system.tes.profile[-1])
                        else:
                            system.conn_15.set_attr(T=system.tes.profile[-1])
                except Exception as e:
                    print(f"Warning: could not recreate network in attempt_to_solve: {e}")
                
                # Incrementally adjust parameters and randomize
                if k == 2:
                    self._randomize_conn_guesses(system, TESmode, seed=None,
                                                 T_bounds=(350.0, 550.0),
                                                 include=('T0'))
                elif k == 3:
                    self._randomize_conn_guesses(system, TESmode, seed=None,
                                                 T_bounds=(300.0, 600.0),
                                                 include=('T0', 'm0'))
                elif k == 4:
                    self._randomize_conn_guesses(system, TESmode, seed=None,
                                                 T_bounds=(250.0, 650.0),
                                                 include=('T0', 'm0', 'p0'))
                else:
                    self._randomize_conn_guesses(system, TESmode, seed=None,
                                                 T_bounds=(200.0, 700.0),
                                                 include=('T0', 'm0', 'p0'))
            try:
                # Desactiva trazas verbosas si corresponde
                try:
                    system.network.set_attr(iterinfo=False)
                except AttributeError:
                    pass
    
                warm_start = (mode == 'offdesign' and TESmode in ['1', '2'])
                system.solve_network(mode=mode, design_path=design_path, TESmode=TESmode,
                                     use_init_path=warm_start)
                conv = bool(getattr(system.network, 'converged', False))
                attempts.append({'mode': TESmode, 'try_idx': k, 'tespy_converged': conv})
                if conv:
                    self.current_mode = TESmode
                    return True, attempts, None
                else:
                    last_err = "TESPy did not converge."
                    print(f"[attempt_to_solve] Attempt {k} failed to converge. Retrying...")
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                attempts.append({'mode': TESmode, 'try_idx': k, 'tespy_converged': False, 'error': str(e)})
                print(f"[attempt_to_solve] Attempt {k} exception: {e}. Retrying...")
                
        # Si llegamos aquÃ­ sin retornar, fallaron todos los intentos
        if TESmode != '4':
            print(f"[attempt_to_solve] Solver failed after {tries} attempts for mode {TESmode}. Falling back to Mode 4.")
            self.current_mode = '4'
            try:
                system.set_operation_mode(TESmode='4', mode=mode, current_irr=self.current_irr, profile=system.tes.profile if hasattr(system, 'tes') else None)
                system.solve_network(mode=mode, design_path='base_design_4', TESmode='4')
                if bool(getattr(system.network, 'converged', False)):
                    attempts.append({'mode': '4', 'try_idx': 'fallback', 'tespy_converged': True})
                    return True, attempts, last_err
            except Exception as fallback_err:
                last_err = f"{last_err} | Fallback Mode 4 failed: {fallback_err}"

        raise RuntimeError(f"TESPy solver failed after {tries} attempts. Last error: {last_err}")
                
        # --- Helper: randomizar guesses de conexiones del modo activo -------------
    def _randomize_conn_guesses(self, system, TESmode, *, seed=None,
                                T_bounds=None, include=('T0')):
        """
        Randomiza los 'initial guesses' de las conexiones disponibles en el modo
        actual para ayudar a la convergencia.
        """
        rng = np.random.default_rng(seed)
        if T_bounds is None:
            T_bounds = (300.0, 600.0)

        randomized = []
        active_labels = set(system.network.conns.index) if hasattr(system.network, 'conns') else set()
        for name in dir(system):
            if not name.startswith('conn_'):
                continue
            conn = getattr(system, name, None)
            if conn is None or not hasattr(conn, 'set_attr'):
                continue
            # Skip stale connections not in current network
            if hasattr(conn, 'label') and conn.label is not None:
                if str(conn.label) not in active_labels:
                    continue
            try:
                if 'T0' in include:
                    T0 = float(rng.uniform(*T_bounds))
                    conn.set_attr(T0=T0)
                if 'm0' in include:
                    m0 = float(rng.uniform(20.0, 50.0))
                    conn.set_attr(m0=m0)
                if 'p0' in include:
                    p0 = float(rng.uniform(1.0, 10.0))
                    conn.set_attr(p0=p0)
                if 'h0' in include:
                    h0 = float(rng.uniform(500.0, 1000.0))
                    conn.set_attr(h0=h0)
                randomized.append(name)
            except ValueError:
                continue

        print(f"[attempt_to_solve] Randomized initial guesses ({include}) en modo {TESmode}:",
              f"{len(randomized)} conns")

        return randomized

    
    def _get_inlet_conn(self, comp, system):
        if comp is None:
            return None
        if hasattr(comp, 'inl') and len(comp.inl) > 0:
            return comp.inl[0]
        return None

    def _get_outlet_conn(self, comp, system):
        if comp is None:
            return None
        if hasattr(comp, 'outl') and len(comp.outl) > 0:
            return comp.outl[0]
        return None

    def _iterate_tes_coupling(self, system,
                              mode='design', TESmode='2', 
                              design_path='base_design',
                              Tamb=25):
        """
        Performs the inner iteration between the TES 1D model and
        the TESPy network for one 'steady' scenario (or one time-step).

        - Sets initial guess for TES-HX side from the top/bottom of the TES 
          depending on 'charge' or 'discharge'.
        - Iterates until we pass the convergence or divergence check, 
          or until hitting max_iter.
        """
        max_iter = 20
        T_out_history = []
        conv_factors  = []
        self.TES_profiles = []
        
        # --- logging de convergencia por paso (no altera la lógica ni las ecuaciones) ---
        iter_info = {
            'initial_mode': TESmode,
            'final_mode': None,
            'status': None,            # 'converged' | 'diverged' | 'max_iter'
            'attempts': [],            # lista de dicts: {mode, tespy_converged, iter_idx}
            'tespy_error': None,       # reservado: si capturas algún error de TESPy
            'dof_report': None,        # reservado: grados de libertad / diagnóstico si lo expones
        }
        self._last_iter_info = None    # se poblará al final del paso
        tank_cfg = getattr(system, 'tank_config', 'indirect')
        is_series_direct_m1 = (TESmode == '1' and tank_cfg == 'direct'
                               and getattr(system, 'topology', 'Parallel') == 'Series')
        # 2) Initialize the TES_HX source temperature from top/bottom
        if TESmode in ['1','5','6']:
            if is_series_direct_m1:
                hot_bot = system.hot_tes.profile[-1]
                cold_bot = system.cold_tes.profile[-1]
                system.conn_ht_ph.set_attr(T=hot_bot)
                system.conn_10.set_attr(T=cold_bot)
            elif getattr(self, 'tank_config', 'indirect') == 'direct':
                if hasattr(system, 'charge_tes_hx'):
                    T_in_bot = system.tes.profile[-1]
                    system.conn_10.set_attr(T=T_in_bot)
                else:
                    TESmode = '4'
                    self.current_mode = TESmode
            else:
                if hasattr(system, 'charge_tes_hx'):
                    T_in_bot = system.tes.profile[-1]
                    system.conn_13.set_attr(T=T_in_bot)
                else:
                    TESmode = '4'
                    self.current_mode = TESmode
        elif TESmode in ['3']:
            tank_cfg = getattr(system, 'tank_config', 'indirect')
            if tank_cfg == 'direct':
                system.hot_tes.set_state('discharge')
                system.cold_tes.set_state('discharge')
                T_hot = system.hot_tes.profile[-1]
                T_cold = system.cold_tes.profile[-1]
                if T_cold >= 520.0:
                    T_mix = T_cold
                elif T_hot >= 520.0:
                    T_mix = 520.0
                else:
                    T_mix = T_hot
                system.conn_04.set_attr(T=T_mix)
            else:
                T_in_top = system.tes.profile[-1]
                system.conn_15.set_attr(T=T_in_top)

        mode_3_fail = False
        is_direct_m3 = (TESmode == '3' and tank_cfg == 'direct')
        if is_series_direct_m1 or is_direct_m3:
            old_hot_profile = np.array(system.hot_tes.profile).copy()
            old_cold_profile = np.array(system.cold_tes.profile).copy()
            old_profile = old_hot_profile
        else:
            old_profile = np.array(system.tes.profile).copy()
        for iteration in range(max_iter):
            if mode == 'offdesign':
                system.network.set_attr(iterinfo=False)
                # Propagate design-point TES mass flow so set_operation_mode can constrain it
                if TESmode in ['1', '5', '6'] and hasattr(self, 'charge_tes_m_design'):
                    system.tes_charge_m = self.charge_tes_m_design
                elif TESmode == '3' and hasattr(self, 'discharge_tes_m_design'):
                    system.tes_charge_m = self.discharge_tes_m_design
            ok, att, err = self.attempt_to_solve(system, mode, design_path, TESmode, tries=5)
            TESmode = self.current_mode
            try:
                iter_info['attempts'].append({
                    'mode': TESmode,
                    'tespy_converged': bool(getattr(system.network, 'converged', False)),
                    'iter_idx': iteration + 1,
                })
            except AttributeError:
                pass
            # Revisar convergencia en HX de descarga
            if TESmode in ['3']:
                if getattr(self, 'tank_config', 'indirect') == 'direct':
                    Q_hx = system.conn_04.T.val - system.conn_11.T.val  # proxy: positive if outlet hotter
                    if Q_hx <= 0:
                        mode_3_fail = True
                else:
                    dT_dhx = (system.conn_04.T.val - system.conn_11.T.val) if hasattr(system, 'conn_04') else 0
                    if dT_dhx <= 0:
                        mode_3_fail = True
                if mode_3_fail:
                    iter_info['attempts'].append({
                    'mode': TESmode,
                    'tespy_converged': bool(getattr(system.network, 'converged', False)),
                    'iter_idx': iteration + 1,
                    'ttd_min_if_mode3': dT_dhx,
                    })

            if not system.network.converged:
                if TESmode in ['1','5','6']:
                    print('System did not converge\n',TESmode, ' passing to 2')
                    TESmode = '2'
                    self.current_mode = TESmode
                    system.set_operation_mode(TESmode=TESmode, 
                                              current_irr=self.current_irr,
                                              profile=old_profile,
                                              prev_TES_lay = self.TES_lay)
                    system.network.set_attr(iterinfo=False)
                    self.attempt_to_solve(system, mode, design_path, TESmode, tries=5)
                elif TESmode in ['3']:
                    print('System did not converge\n', TESmode, 'passing to 4')
                    TESmode = '4'
                    self.current_mode = TESmode
                    system.set_operation_mode(TESmode=TESmode, 
                                              current_irr=self.current_irr,
                                              profile=old_profile,
                                              prev_TES_lay = self.TES_lay)
                    system.network.set_attr(iterinfo=False)
                    self.attempt_to_solve(system, mode, design_path, TESmode, tries=5)
                else:
                    self.attempt_to_solve(system, mode, design_path, TESmode, tries=5)
                    if not system.network.converged:
                        print(f"[WARNING] TESPy solver did not converge at iteration {iteration+1}.")
                        break
            if mode_3_fail:
                # DHX exhausted — accept partial discharge, don't fall back to Mode 4
                profile = system.tes.profile
                old_profile = system.tes.calc_heat_loss(profile, 3600, Tamb)
                system.tes.profile = old_profile
                iter_info['status'] = 'converged'
                iter_info['final_mode'] = TESmode
                self.TES_profiles.append(old_profile)
                break
            if TESmode in ['2', '4']:
                status = 'converged'
                if getattr(system, 'tank_config', 'indirect') == 'direct':
                    hot_p = system.hot_tes.profile
                    cold_p = system.cold_tes.profile
                    old_hot_profile = system.hot_tes.calc_heat_loss(hot_p, 3600, Tamb)
                    old_cold_profile = system.cold_tes.calc_heat_loss(cold_p, 3600, Tamb)
                    system.hot_tes.profile = old_hot_profile
                    system.cold_tes.profile = old_cold_profile
                    old_profile = old_hot_profile
                else:
                    profile = system.tes.profile
                    old_profile = system.tes.calc_heat_loss(profile, 3600, Tamb)
                    system.tes.profile = old_profile
                iter_info['status'] = 'converged'
                iter_info['final_mode'] = TESmode
                self.TES_profiles.append(old_profile)
                break
            # b) Read new TES inlet conditions from TES_HX outlet
            if TESmode in ['1','5','6']:
                if is_series_direct_m1:
                    T_hot_in = system.conn_02.T.val
                    m_hot_in = system.conn_02.m.val_SI
                    T_cold_in = system.conn_06.T.val
                    m_cold_in = system.conn_06.m.val_SI
                elif getattr(self, 'tank_config', 'indirect') == 'direct':
                    topo = getattr(system, 'topology', 'Parallel')
                    if TESmode == '1':
                        inlet_conn = system.conn_09 if topo == 'Parallel' else system.conn_06
                    elif TESmode == '5':
                        inlet_conn = system.conn_02
                    else:
                        inlet_conn = system.conn_02 if topo == 'Parallel' else system.conn_06
                    T_tes_in = inlet_conn.T.val
                    m_tes_in = inlet_conn.m.val_SI
                else:
                    T_tes_in = system.conn_14.T.val
                    m_tes_in = system.conn_14.m.val_SI
            elif TESmode in ['3']:
                if getattr(self, 'tank_config', 'indirect') == 'direct':
                    T_tes_in = system.conn_11.T.val
                    m_tes_in = system.conn_11.m.val_SI
                else:
                    T_tes_in = system.conn_16.T.val
                    m_tes_in = system.conn_16.m.val_SI
            if is_series_direct_m1:
                if m_hot_in < 0.01 or m_cold_in < 0.01:
                    self.mode_alert = True
                    iter_info['status'] = 'diverged'
                    iter_info['final_mode'] = TESmode
                    print('TES mass flow alert (two-tank)')
                    break
            elif TESmode in ['1','5','6','3']:
                if m_tes_in < 0.01:
                    self.mode_alert = True
                    iter_info['status'] = 'diverged'
                    iter_info['final_mode'] = TESmode
                    print('TES mass flow alert')
                    break

            if is_series_direct_m1 or is_direct_m3:
                if is_series_direct_m1:
                    system.hot_tes.update_temperature_profile(
                        T_in=T_hot_in, mass_flow=m_hot_in,
                        initial_profile=old_hot_profile)
                    system.cold_tes.update_temperature_profile(
                        T_in=T_cold_in, mass_flow=m_cold_in,
                        initial_profile=old_cold_profile)
                else:
                    # Mode 3 direct discharging:
                    # 1. Compute splits analytically
                    T_hot = old_hot_profile[-1]
                    T_cold = old_cold_profile[-1]
                    if T_cold >= 520.0:
                        x_hot = 0.0
                        x_cold = 1.0
                    elif T_hot >= 520.0:
                        x_hot = (520.0 - T_cold) / (T_hot - T_cold)
                        x_cold = 1.0 - x_hot
                    else:
                        x_hot = 1.0
                        x_cold = 0.0
                    m_hot = x_hot * m_tes_in
                    m_cold = x_cold * m_tes_in
                    # 2. Update both tank profiles using T_tes_in (process return T)
                    system.hot_tes.update_temperature_profile(
                        T_in=T_tes_in, mass_flow=m_hot,
                        initial_profile=old_hot_profile)
                    system.cold_tes.update_temperature_profile(
                        T_in=T_tes_in, mass_flow=m_cold,
                        initial_profile=old_cold_profile)
                T_hot_out = system.hot_tes.tout
                T_cold_out = system.cold_tes.tout
                if is_direct_m3:
                    if T_cold_out >= 520.0:
                        T_tes_out = T_cold_out
                    elif T_hot_out >= 520.0:
                        T_tes_out = 520.0
                    else:
                        T_tes_out = T_hot_out
            else:
                system.tes.update_temperature_profile(
                    T_in=T_tes_in,
                    mass_flow=m_tes_in,
                    initial_profile=old_profile)
                T_tes_out = system.tes.tout

            # d) Set the new outlet temperature to the HX inlet for next iteration
            if TESmode in ['1','5','6']:
                if is_series_direct_m1:
                    system.conn_ht_ph.set_attr(T=T_hot_out)
                    system.conn_10.set_attr(T=T_cold_out)
                elif getattr(self, 'tank_config', 'indirect') == 'direct':
                    system.conn_10.set_attr(T=T_tes_out)
                else:
                    system.conn_13.set_attr(T=T_tes_out)
                self.TES_lay = 'Charge'
            elif TESmode in ['3']:
                if getattr(self, 'tank_config', 'indirect') == 'direct':
                    system.conn_04.set_attr(T=T_tes_out)
                else:
                    system.conn_15.set_attr(T=T_tes_out)
                self.TES_lay = 'Discharge'

            # e) Track T_out for our multi-step convergence logic
            # e) Track T_out for our multi-step convergence logic
            if is_series_direct_m1 or is_direct_m3:
                T_out_history.append(T_hot_out)
            else:
                T_out_history.append(T_tes_out)
            if len(T_out_history) > 1:
                prev_T = T_out_history[-2]
                if abs(prev_T) > 1e-6:
                    if is_series_direct_m1 or is_direct_m3:
                        cf = abs(T_hot_out - prev_T) / abs(prev_T)
                    else:
                        cf = abs(T_tes_out - prev_T) / abs(prev_T)
                else:
                    cf = 0.0
                conv_factors.append(cf)

            # f) Evaluate our custom convergence criteria
            status = self._check_tes_convergence(T_out_history, conv_factors)
            if mode == 'design':
                if is_series_direct_m1 or is_direct_m3:
                    print(f'Hot TES outlet: {T_hot_out:.1f} C, Cold TES outlet: {T_cold_out:.1f} C')
                else:
                    print(f'outlet TES temperature: {T_tes_out}')
            if status == 'converged':
                iter_info['status'] = 'converged'
                iter_info['final_mode'] = TESmode
                if getattr(system, 'tank_config', 'indirect') == 'direct':
                    hot_p = system.hot_tes.profile
                    cold_p = system.cold_tes.profile
                    old_hot_profile = system.hot_tes.calc_heat_loss(hot_p, 3600, Tamb)
                    old_cold_profile = system.cold_tes.calc_heat_loss(cold_p, 3600, Tamb)
                    system.hot_tes.profile = old_hot_profile
                    system.cold_tes.profile = old_cold_profile
                    old_profile = old_hot_profile
                else:
                    profile = system.tes.profile
                    old_profile = system.tes.calc_heat_loss(profile, 3600, Tamb)
                    system.tes.profile = old_profile
                self.TES_profiles.append(old_profile)
                break
            elif status == 'diverged':
                print(f"[WARNING] TES iteration diverging at iteration {iteration+1}!")
                break
        else:
            # If we never hit a 'break', we didn't converge within max_iter
            iter_info['status'] = 'max_iter'
            iter_info['final_mode'] = TESmode
            print("[WARNING] Reached max iteration count without TES convergence.")
        self.current_mode = TESmode

        # Exponer logging del paso (para usarlo en run_quasi_steady_simulation)
        self._last_iter_info = iter_info
        return iter_info
    # -------------------------------------------------------------------------
    # 3) Steady-State Solver
    # -------------------------------------------------------------------------
    def solve_network_steady(self, mode='design', TESmode=None):
        """
        Public method to solve the system in a stationary (steady) mode,
        including iteration with the TES if present.

        Args:
            operation_mode (str): 'charge' or 'discharge'.
            design_path (str): path to the saved design data (for offdesign mode).
        """
        # Simply call our coupling iteration for one single "steady" step
        system = self.solar_system
        #self.TES_lay = 'Charge'
        self.prev_TESmode = '4'
        self.current_irr = self.irr
        if TESmode is None:
            TESmode = self.get_mode(self.irr, system.tes.profile, self.TES_lay)
        print(f'TES mode {TESmode}')
        design_path = f'base_design_{TESmode}'
        system.set_operation_mode(TESmode=TESmode, 
                                             current_irr=self.irr, 
                                             profile=system.tes.profile,
                                             prev_TES_lay = self.TES_lay,
                                             mode=mode)

        self._iterate_tes_coupling(mode=mode, system = system,
                                   TESmode=TESmode, design_path=design_path,
                                   Tamb = 25)
    def _collect_step_signals(self, system, mode: str) -> dict:
        """
        SeÃ±ales del paso actual medidas directamente en los componentes:
          EnergÃ­as por paso (kJ): to_tes, tes_to_proc, solar_to_proc, aux_to_proc, ptc_total
          Temperaturas [Â°C]:      T_ptc_out, T_tes_top, T_tes_bottom
          Flujos mÃ¡sicos [kg/s]:  mdot_ptc, mdot_tes_charge, mdot_tes_discharge, mdot_process
    
        Correcciones:
        - Q de HX se toma como |Q| (signo en TESPy depende del lado).
        - Puertas lÃ³gicas por estado del TES para cargar/descargar (anula el opuesto).
        """
    

        # ---------- utilidades robustas ----------
        def _get_comp(sys, *names):
            for n in names:
                c = getattr(sys, n, None)
                if c is not None:
                    return c
            return None
    
        def _get_Q_kw(comp) -> float:
            """Intenta comp.Q.val (o comp.Q) y devuelve |Q| en kW; 0 si no disponible."""
            if comp is None:
                return 0.0
            
            # If it's a pipe, we can calculate Q from the streams
            if type(comp).__name__ == 'Pipe':
                try:
                    h_in = self._get_inlet_conn(comp, system).h.val_SI
                    h_out = comp.outl[0].h.val_SI
                    m = self._get_inlet_conn(comp, system).m.val_SI
                    if h_in is not None and h_out is not None and m is not None:
                        return abs(m * (h_in - h_out) / 1000.0)
                except Exception:
                    pass

            for a in ['Q']:
                qa = getattr(comp, a, None)
                if qa is None:
                    continue
                v = getattr(qa, 'val', None)
                if v is None:
                    try:
                        v = float(qa)
                    except (ValueError, TypeError):
                        v = None
                if v is not None and np.isfinite(v):
                    return abs(float(v))  # <<< valor absoluto: evita falsos 0 por signo
            return 0.0
    
        def _conn_T(comp):
            """Temperatura de salida si existe (Â°C)."""
            try:
                if comp is None:
                    return np.nan
                if self._get_outlet_conn(comp, system) and self._get_outlet_conn(comp, system) is not None:
                    v = getattr(getattr(self._get_outlet_conn(comp, system), 'T', None), 'val', None)
                    if v is None:
                        v = getattr(self._get_outlet_conn(comp, system), 'T', None)
                    return float(v) if v is not None else np.nan
            except (AttributeError, IndexError, TypeError):
                pass
            return np.nan
    
        def _mdot_kg_s(comp):
            """Flujo mÃ¡sico de salida si existe (kg/s)."""
            try:
                if comp is None:
                    return np.nan
                if self._get_outlet_conn(comp, system) and self._get_outlet_conn(comp, system) is not None:
                    v = getattr(getattr(self._get_outlet_conn(comp, system), 'm', None), 'val', None)
                    if v is None:
                        v = getattr(self._get_outlet_conn(comp, system), 'm', None)
                    return float(v) if v is not None else np.nan
            except (AttributeError, IndexError, TypeError):
                pass
            return np.nan
    
        # ---------- componentes ----------
        ptc     = _get_comp(system, 'ptc_field')
        if mode == '5':
            hx_chg = _get_comp(system, 'high_t_charge_pipe', 'high_t_charge_hx')
        else:
            hx_chg = _get_comp(system, 'hot_tank_hx', 'hot_tes_pipe', 'charge_tes_pipe', 'charge_tes_hx')
        hx_chg2 = _get_comp(system, 'cold_tank_hx', 'cold_tes_pipe')
        hx_dch  = _get_comp(system, 'discharge_tes_pipe', 'discharge_tes_hx')
        hx_proc = _get_comp(system, 'process_hx')
        hx_aux  = _get_comp(system, 'preheater_hx')

        tes_state = ''
        try:
            tes_state = str(getattr(system.tes, 'state', '')).lower()
        except AttributeError:
            pass

        # ---------- time step (seconds) ----------
        dt_s = 3600.0  # 1-hour time step, consistent with simulation loop

        # ---------- read actual energy values from components ----------
        q_ptc_kw = _get_Q_kw(ptc)
        q_chg_kw = _get_Q_kw(hx_chg)
        if hasattr(system, 'cold_tes_pipe') and system.cold_tes_pipe is not None:
            q_chg_kw += _get_Q_kw(hx_chg2)
        q_dch_kw = _get_Q_kw(hx_dch)
        q_aux_kw = _get_Q_kw(hx_aux)
        q_proc_kw = _get_Q_kw(hx_proc)

        # ---------- mode-gating: zero out physically impossible contributions ----------
        if mode in ['1','5','6']:
            q_dch_kw = 0.0
        elif mode in ['3']:
            q_chg_kw = 0.0
            q_ptc_kw = 0.0
        else:
            # standby / Mode 2: no TES interaction
            q_chg_kw = 0.0
            q_dch_kw = 0.0
    
        # ---------- energÃ­as por paso (kJ) ----------
        to_tes_kJ        = q_chg_kw * dt_s
        tes_to_proc_kJ   = q_dch_kw * dt_s
        ptc_total_kJ     = q_ptc_kw * dt_s
    
        # Auxiliar â†’ proceso solo cuando no hay solar directo (misma regla de antes)
        aux_to_proc_kJ   = (0.0 if mode in ['1','2'] else q_aux_kw) * dt_s
    
        # Solar â†’ proceso directo (mediciÃ³n compuesta mÃ­nima), sin balances detallados:
        # PTC total menos lo que se desvÃ­a a cargar el TES.
        solar_to_proc_kJ = max(ptc_total_kJ - to_tes_kJ, 0.0)
    
        # ---------- temperaturas ----------
        T_ptc_out   = _conn_T(ptc)
        if mode not in ['1','2','6']:
            T_ptc_out = np.nan
        # perfil TES para top/bottom igual que en tus plots
        T_tes_top = np.nan
        T_tes_bot = np.nan
        T_tes_cold_top = np.nan
        T_tes_cold_bot = np.nan
        try:
            is_sd = hasattr(system, 'cold_tes') and system.cold_tes is not None
            if is_sd:
                hot_arr = np.array(system.hot_tes.profile).ravel()
                if hot_arr.size > 0:
                    hp = hot_arr[::-1] if mode in ['1','5','6'] else hot_arr
                    T_tes_bot = float(hp[0])
                    T_tes_top = float(hp[-1])
                cold_arr = np.array(system.cold_tes.profile).ravel()
                if cold_arr.size > 0:
                    cp = cold_arr[::-1] if mode in ['1','5','6'] else cold_arr
                    T_tes_cold_bot = float(cp[0])
                    T_tes_cold_top = float(cp[-1])
            else:
                prof_raw = None
                if hasattr(self, 'TES_profiles') and self.TES_profiles is not None:
                    pr_val = self.TES_profiles
                    arr = np.array(pr_val[-1] if isinstance(pr_val, (list, tuple)) and len(pr_val) > 0 else pr_val).ravel()
                    prof_raw = arr if arr.size > 0 else None
                elif hasattr(system, 'tes') and hasattr(system.tes, 'profile'):
                    arr = np.array(system.tes.profile).ravel()
                    prof_raw = arr if arr.size > 0 else None
                if prof_raw is not None:
                    prof = prof_raw[::-1] if mode in ['1','5','6'] else prof_raw
                    T_tes_bot = float(prof[0])
                    T_tes_top = float(prof[-1])
        except (IndexError, TypeError, ValueError, AttributeError):
            pass
    
        # ---------- flujos mÃ¡sicos ----------
        mdot_ptc          = _mdot_kg_s(ptc)
        mdot_tes_charge   = _mdot_kg_s(hx_chg)
        mdot_tes_discharge= _mdot_kg_s(hx_dch)
        mdot_process      = _mdot_kg_s(hx_proc)

        # puertas lÃ³gicas tambiÃ©n para á¹ (coherente con potencias)
        if mode in ['1','5','6']:
            mdot_tes_discharge = 0.0
        elif mode in ['3']:
            mdot_tes_charge = 0.0
            mdot_ptc = 0.0
        else:
            mdot_tes_charge    = 0.0
            mdot_tes_discharge = 0.0
            mdot_ptc           = 0.0 if mode == '4' else mdot_ptc  # Mode 2 has PTC

        # ---------- pump power fallback ----------
        pump_kw = None
        for p_name in ['pump', 'pump2', 'comp']:
            comp = _get_comp(system, p_name)
            if comp is not None and getattr(comp, 'P', None) is not None:
                val = getattr(comp.P, 'val', None)
                if val is not None and np.isfinite(val):
                    if pump_kw is None:
                        pump_kw = 0.0
                    pump_kw += abs(float(val)) / 1000.0
        
        if pump_kw is None:
            # Fallback calculation
            mdot_vals = [mdot_ptc, mdot_tes_charge, mdot_tes_discharge, mdot_process]
            mdot_max = max([0.0 if (m is None or np.isnan(m)) else float(m) for m in mdot_vals])
            density = 1850.0  # kg/m3 approx for molten salt
            delta_P = 500000.0  # Pa (5 bar)
            efficiency = 0.75
            if mdot_max > 0:
                pump_kw = (mdot_max * delta_P / (density * efficiency)) / 1000.0
            else:
                pump_kw = 0.0

        net_conv = bool(getattr(system.network, 'converged', False))
        return dict(
            # energÃ­as
            to_tes_kJ=to_tes_kJ,
            tes_to_proc_kJ=tes_to_proc_kJ,
            solar_to_proc_kJ=solar_to_proc_kJ,
            aux_to_proc_kJ=aux_to_proc_kJ,
            ptc_total_kJ=ptc_total_kJ,
            # temperaturas
            T_ptc_out=T_ptc_out,
            T_tes_top=T_tes_top,
            T_tes_bottom=T_tes_bot,
            T_tes_cold_top=T_tes_cold_top,
            T_tes_cold_bot=T_tes_cold_bot,
            # flujos mÃ¡sicos
            mdot_ptc_kg_s=mdot_ptc,
            mdot_tes_charge_kg_s=mdot_tes_charge,
            mdot_tes_discharge_kg_s=mdot_tes_discharge,
            mdot_process_kg_s=mdot_process,
            pump_power_kW=pump_kw,
            process_hx_Q_kW=q_proc_kw,
            network_converged=net_conv)
    


    def run_quasi_steady_simulation(self, days_to_simulate = 10,
                                    csv = 'TMY.csv', time_col='Fecha/Hora',
                                    E_col='dni', Tamb_col='temp'):
        """
        Existing method: only the snippet showing how to call _iterate_tes_coupling now.
        """
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF,
                                    topology=self.topology,
                                    tank_config=self.tank_config
                                    )
        self.solar_system.create_network(mode=4)
        self.results = []
        
        self.TES_lay = 'Charge'
        self.prev_TESmode = '4'
        self.current_irr = 0
        data_frame = self.load_data(csv, '2022-01-01', days_to_simulate=days_to_simulate)
        # Track total runtime
        print("\n=== Starting transient simulation ===")
        start_time = time.time()

        self.solar_system.tes.t_max = 600
        if hasattr(self.solar_system, 'cold_tes') and self.solar_system.cold_tes is not None:
            self.solar_system.cold_tes.t_max = 600
        self._mode_dwell = 0
        
        # Reset TES profile to initial temperature
        T_init = self.tes_params.get('Initial temperature', 550)
        self.solar_system.tes.profile = np.ones(20) * T_init
        if hasattr(self.solar_system, 'cold_tes') and self.solar_system.cold_tes is not None:
            self.solar_system.cold_tes.profile = np.ones(20) * T_init
        
        for idx, row in tqdm(data_frame.iterrows(), total=len(data_frame), desc="Simulating"):
            
            self.mode_alert = False
            current_irr = row[E_col]
            self.current_irr = current_irr
            current_Tamb = row[Tamb_col]
            
            # Decide TES mode
            new_TESmode = self.get_system_mode(current_irr)

            if self.zinc_pool is not None:
                self.solar_system._zinc_pool_T06 = (
                    self.zinc_pool.process_outlet_temp())

            self.solar_system.set_operation_mode(TESmode=new_TESmode, 
                                                 current_irr=current_irr,
                                                 profile=self.solar_system.tes.profile,
                                                 prev_TES_lay = self.TES_lay,
                                                 mode='offdesign')
            self.current_mode = new_TESmode

            if self.current_mode in ['1','2','5','6']:
                self.solar_system.ptc_field.set_attr(E=current_irr, Tamb=current_Tamb)

            # Zinc pool: override process outlet temperature
            if self.zinc_pool is not None:
                t06_zn = self.zinc_pool.process_outlet_temp()
                if hasattr(self.solar_system, 'conn_06') and self.solar_system.conn_06 is not None:
                    self.solar_system.conn_06.set_attr(T=t06_zn)

            design_path = f'base_design_{self.current_mode}'
            
            # For each time step, do the same iteration
            iter_info = self._iterate_tes_coupling(mode='offdesign', system =self.solar_system,
                                       TESmode=self.current_mode, design_path=design_path,
                                       Tamb=current_Tamb) 
            if self.mode_alert:
                self.current_mode = '4'
                self.solar_system.set_operation_mode(TESmode='4', 
                                                     current_irr=current_irr,
                                                     profile=self.solar_system.tes.profile,
                                                     prev_TES_lay = self.TES_lay)
                self._iterate_tes_coupling(mode='offdesign', system =self.solar_system,
                                               TESmode=self.current_mode, design_path=design_path,
                                               Tamb=current_Tamb) 
                        #print(new_TESmode)
            signals = self._collect_step_signals(self.solar_system, self.current_mode)

            if self.zinc_pool is not None:
                Q_to_proc_kW = signals.get('process_hx_Q_kW', 0.0) / 1000.0
                self.zinc_pool.update(
                    Q_in_kW=Q_to_proc_kW, dt_s=3600.0,
                    T_amb=current_Tamb, timestamp=row[time_col])

            # Clamp TES profile to valid CoolProp range
            if hasattr(self.solar_system, 'tes') and self.solar_system.tes.profile is not None:
                self.solar_system.tes.profile = np.clip(
                    self.solar_system.tes.profile, 300.1, 600.0)
            if hasattr(self.solar_system, 'cold_tes') and self.solar_system.cold_tes is not None:
                self.solar_system.cold_tes.profile = np.clip(
                    self.solar_system.cold_tes.profile, 300.1, 600.0)
            if hasattr(self.solar_system, 'cold_tes') and self.solar_system.cold_tes is not None:
                tes_soc_kWh = (self.solar_system.hot_tes.calculate_SoC(self.solar_system.hot_tes.profile)
                               + self.solar_system.cold_tes.calculate_SoC(self.solar_system.cold_tes.profile))
            else:
                tes_soc_kWh = self.solar_system.tes.calculate_SoC(self.solar_system.tes.profile)
            # Standardize energy accounting to use _collect_step_signals which properly handles units (W -> kJ)
            Q_ptc_kJ = signals.get('ptc_total_kJ', 0.0)
            Q_ph_kJ = signals.get('aux_to_proc_kJ', 0.0)
            pump_power = signals.get('pump_power_kW', 0.0) * 1000.0
            self.results.append({
                'time': row[time_col],
                'E': current_irr,
                'Tamb': current_Tamb,
                'ptc_energy_kJ': Q_ptc_kJ,
                'ph_energy_kJ':  Q_ph_kJ,
                'pump_power_W':  pump_power,
                'TES_profiles': self.TES_profiles,
                'TES_layout': self.solar_system.tes.state,
                'TESmode': self.current_mode,
                # --- energÃ­as directas por paso ---
                'to_tes_kJ':          signals['to_tes_kJ'],
                'tes_to_proc_kJ':     signals['tes_to_proc_kJ'],
                'solar_to_proc_kJ':   signals['solar_to_proc_kJ'],
                'aux_to_proc_kJ':     signals['aux_to_proc_kJ'],
                'ptc_total_kJ':       signals['ptc_total_kJ'],
                
                # --- temperaturas relevantes ---
                'T_ptc_out':          signals['T_ptc_out'],
                'T_tes_top':          signals['T_tes_top'],
                'T_tes_bottom':       signals['T_tes_bottom'],
                
                # --- flujos mÃ¡sicos relevantes ---
                'mdot_ptc_kg_s':          signals['mdot_ptc_kg_s'],
                'mdot_tes_charge_kg_s':   signals['mdot_tes_charge_kg_s'],
                'mdot_tes_discharge_kg_s':signals['mdot_tes_discharge_kg_s'],
                'mdot_process_kg_s':      signals['mdot_process_kg_s'],
                
                # --- SoC (energÃ­a, NO acumulado) ---
                'tes_soc_kWh':        tes_soc_kWh,
                
                # --- logging de convergencia por paso ---
                'mode_initial':        iter_info.get('initial_mode'),
                'mode_final':          iter_info.get('final_mode'),
                'iter_status':         iter_info.get('status'),            # 'converged'|'diverged'|'max_iter'
                'attempt_count':       len(iter_info.get('attempts', [])),
                'attempted_modes':     [a.get('mode') for a in iter_info.get('attempts', [])],
                'attempts_json':       iter_info.get('attempts', []),      # serializable a CSV (json.dumps)
                'network_converged':   signals.get('network_converged', None),
                'tespy_error':         iter_info.get('tespy_error'),
                'dof_report':          iter_info.get('dof_report'),
                # --- zinc pool (dynamic process model, None if disabled) ---
                'zinc_pool_temp':  (self.zinc_pool.temperature
                                    if self.zinc_pool is not None else None),
                'process_hx_Q_kW': signals.get('process_hx_Q_kW', 0.0),
                            })
            
            self.prev_TESmode = self.current_mode

        # End of simulation: print total elapsed time
        end_time = time.time()
        total_runtime = end_time - start_time
        print(f"\nTransient simulation completed in {total_runtime:.2f} seconds.")

        return self.results

    def compute_performance_metrics(self):
        """
        Process self.results to compute plant factor, comp energy consumption, etc.

        Args:
            process_demand_kJ (float, optional): 
                Total heat demanded by the process (in kJ) 
                over the entire simulation horizon, if known.

        Returns:
            dict: A dictionary of computed metrics.
        """
        self.dt_hours = 1.0
        df = pd.DataFrame(self.results)
        total_ptc_energy_kJ = df['ptc_energy_kJ'].sum()
        total_ph_energy_kJ  = df['ph_energy_kJ'].sum()#.loc[df['ph_energy_kJ'] > 0].sum()
        # pump power (W) * 3600 s for each step (assuming dt=1h)
        total_pump_energy_kJ = (df['pump_power_W'] * 3600.0 * self.dt_hours).sum() / 1000
        
        # Convert kJ to MWh (1 MWh = 3.6e6 kJ)
        ptc_energy_GWh   = total_ptc_energy_kJ / 3.6e9
        ph_energy_GWh    = total_ph_energy_kJ  / 3.6e9
        pump_energy_MWh  = total_pump_energy_kJ / 3.6e6
        
        # Plant factor and Solar fraction
        total_thermal_energy = total_ptc_energy_kJ + total_ph_energy_kJ
        solar_fraction = total_ptc_energy_kJ / total_thermal_energy if total_thermal_energy > 0 else 0
        spf = total_ptc_energy_kJ / (total_thermal_energy + total_pump_energy_kJ) if (total_thermal_energy + total_pump_energy_kJ) > 0 else 0

        # Print performance summary line by line
        print("\n=== Performance Summary ===")
        print(f"Total PTC Energy:       {ptc_energy_GWh:6.2f} GWh")
        print(f"Total Preheater Energy:{ph_energy_GWh:6.2f} GWh")
        print(f"Total Pump Energy:      {pump_energy_MWh:6.2f} MWh")
        print(f"Solar Fraction:         {solar_fraction * 100:6.2f}%")
        print(f"Solar Plant Factor:     {spf * 100:6.2f}%")
        print("================================\n")

        return {'spf': spf, 'solar_fraction': solar_fraction}
