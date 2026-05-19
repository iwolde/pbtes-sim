"""
core.py

This module contains:
1) The SolarThermalSystem class, which builds and solves a TESPy network
   with supercritical CO2 as the working fluid, a compressor, a parabolic
   trough collector, and a simple process heat exchanger.

2) The Reporting class, which handles plotting of results from a parametric
   analysis or time-step simulation.

All methods are commented with details on their purpose and functionality.
"""
import tespy.networks as tpn
import tespy.connections as tpcn
import tespy.components as tpc
import tespy.tools.document_models as ttdm
from tespy.components.heat_exchangers.parabolic_trough import ParabolicTrough
import matplotlib.pyplot as plt
from tqdm import tqdm
import time
import pandas as pd
import numpy as np
import CoolProp.CoolProp as cp
from scipy.optimize import brentq
from scipy.interpolate import interp1d

class PTCField(ParabolicTrough):
    """
    A parabolic trough collector field composed of several parallel rows.

    This subclass internally divides the inlet mass flow among the rows,
    calculates as if there's only one row, and then scales Q, Qloss, etc.
    by the number of rows.
    """

    def __init__(self, label, rows=1, modules=1, **kwargs):
        """
        Parameters
        ----------
        label : str
            The label for the collector.
        rows : int
            Number of identical parallel rows in the solar field.
        kwargs :
            Any additional keyword arguments you want to pass to
            the parent ParabolicTrough constructor (e.g. collector geometry).
        """
        super().__init__(label, **kwargs)
        self.rows = rows
        self.modules = modules

        # We'll store the "single module pr" here if the user sets it
        self.pr_module = None

    def calc_parameters(self):
        """
        Override the parent's calculation routine to:
          - Temporarily reduce mass flow to 1/rows,
          - Call parent calculations,
          - Scale the results by rows,
          - Restore total flow at the outlet.
        """
        # 1) Store total inlet mass flow and total area
        total_m_in = self.inl[0].m.val_SI
        
        # 2) Scale both mass flow and area for a single-row
        if self.rows > 1:
            # Inlet flow
            self.inl[0].m.val_SI = total_m_in / self.rows


        # 3) Run the usual collector calculation (for the scaled single-row)
        super().calc_parameters()

        # 4) Scale Q and Q_loss from single-row to total field
        if self.rows > 1:
            # self.Q is a ComponentProperties object
            self.Q.val_SI *= self.rows
            # self.Q_loss may not always be present, so check first
            if hasattr(self, 'Q_loss'):
                self.Q_loss.val_SI *= self.rows

        # 5) Restore the total mass flow and total area on the outlet and component
        self.outl[0].m.val_SI = total_m_in
      
class ThermalEnergyStorage:
    """
    Manages the thermal energy storage with capability to store, release, or maintain energy,
    simulating temperature profiles and managing energy state.
    """

    def __init__(self, tes_params, name, dt):
        """
        

        Parameters
        ----------
        dt : Int
            Time step.
        tes_params : Dict
            DESCRIPTION.
        name : Str
            TES name.

        Returns
        -------
        None.

        """
        """
        Initializes the thermal energy storage unit.
        :param capacity: float, the energy storage capacity in kWh.
        :param initial_temperature: float, the initial temperature of the storage in degrees Celsius.
        :param name: str, name of the TES module.
        """

        self.dt = dt #min

        self.name = name
        self.state = 'charge'  # default state
        self.inlet = 'top'
        self.outlet = 'bottom'
        self.valve_state = 'off'  # Valve controlling the TES flow
    
        self.initial_temperature = tes_params['Initial temperature']
        self.HT = tes_params['Tank lenght']
        self.Dint = tes_params['Tank diameter']
        self.dp = tes_params['Particle diameter']
        self.e = tes_params['Void fraction']
        self.rho_s = tes_params['Solid density']
        self.cp_s = tes_params['Solid specific heat']
        self.k_s = tes_params['Solid conductivity']
        self.wst = tes_params['Wall thinckness']
        self.kst = tes_params['Tank conductivity']
        self.wins = tes_params['Insulation thickness']
        self.kins = tes_params['Insulatuin conductivity']
        self.AT = 0.25 * self.Dint**2 * np.pi  # m2 - Área transversal del estanque
        self.Aphi = 0.25 * (25.4e-3*2)**2* np.pi  # m2 - Área transversal del tubo de descarga
        
        self.xev = np.linspace(0,1,20)
        self.init = np.ones_like(self.xev)*(self.initial_temperature)
        self.profile = self.init
        self.t_max = self.initial_temperature
        self.t_min = self.initial_temperature
        self.tout = self.initial_temperature
        self.mflow = 0
        self.V_in = 0

    def air_params(self):
        # Temperatura media
        Tav = np.average(self.init)+273.15
        # Propiedades del fluido - Calculados a temperatura media
        self.rho_f = cp.PropsSI('D', 'T', Tav, 'P', 102325, 'air')
        self.cp_f = cp.PropsSI('C', 'T', Tav, 'P', 102325, 'air')
        self.k_f = cp.PropsSI('L', 'T', Tav, 'P', 102325, 'air')
        self.mu_f = cp.PropsSI('V', 'T', Tav, 'P', 102325, 'air')
        
        self.rho_out = cp.PropsSI('D', 'T', self.tout+273.15, 'P', 102325, 'air')
        
    def eq_params(self, T_in, mass_flow):
        """
        

        Parameters
        ----------
        T_in : Float
            Inlet Temperature.
        V_in : Float
            Inlet Velocity.

        Returns
        -------
        None.

        """
 
        self.t_in = T_in
        
        self.mflow = mass_flow #kg/min
        #print(self.mflow)
        
        self.air_params()
        
        # Flujo másico por unidad de área al interior del TES
        G = self.mflow / self.AT 
        # Cálculo de alpha y k_eff
        Re = G*self.dp/self.mu_f  # Reynolds
        Pr = self.mu_f * self.cp_f / self.k_f  # Prandtl
        ff = 6*(1-self.e)/self.dp  # m - Factor de forma roca - fluido
        rho_cp_line = (self.e * self.rho_f * self.cp_f + (1-self.e) * self.rho_s * self.cp_s) # Capacitancia equivalente
        self.kappa = self.e * (self.rho_f * self.cp_f) / rho_cp_line  # Factor kappa (adimensional de interés para el modelo)
        u_in = G / (self.rho_f)  # m/s - Velocidad intersticial
        hv = ff * (self.k_f/self.dp) * 1.32 * Re**0.59 * Pr**(1/3)  # W/m3 K - Coef. de transferencia de calor volumétrica (Tesis Daniel Orellana)
        k_line = (self.e *self.k_f + (1-self.e)*self.k_s) # Conductividad promedio
        k_eff = k_line + ((1-self.e) * (self.rho_s*self.cp_s) * (G*self.cp_f/rho_cp_line))**2/hv  # Conductividad efectiva (Ver ec. 7 de Paper 1)
        alpha = k_eff / rho_cp_line  # Cálculo de alpha
        self.Pe = u_in * self.HT / alpha  # Cálculo de Péclet que cambia con el tiempo (adimensional de interés para el modelo)
        self.a = self.kappa * self.Pe / 2
       
        # Resistencia interna
        hint = (self.k_f/self.dp) * (0.203 * Re**(1/3) * Pr**(1/3) + 0.22 * Re**0.8 * Pr**0.4)
        Rint = 1/hint
        # Coeficiente de transferencia de calor
        hw = 1/Rint
        # Stanton
        self.beta = 4/self.Dint
        self.St = 0.75*hw*self.beta*self.HT/(rho_cp_line*u_in)
        #self.St = 1e-3
        self.b = -(self.St + self.a**2/self.Pe)
        
        self.tau = u_in*self.dt/self.HT
        

    def _eq(self, ev, a):
        """
        Ecuación trascendental para obtener autovalores

        Parameters
        ----------
        ev : TYPE
            DESCRIPTION.
        a : TYPE
            DESCRIPTION.

        Returns
        -------
        eq : TYPE
            DESCRIPTION.

        """
    
        # solve transcendental eq : ev + a * tan(ev) = 0
        eq1 = ev / a
        eq2 = np.tan(ev)
        eq = eq1 + eq2
    
        return eq    
    
    def solve_eq(self, Nroots, a):
        """
        Algoritmo de búsqueda de raíces

        Parameters
        ----------
        Nroots : Roots number.
        a : Parameter a.

        Returns
        -------
        rts : Roots.

        """
        
        # Allocate space
        rts = np.zeros(Nroots)
        # Margin to stay away from poles
        margin = 1e-5
        # First solution
        left = 0
        right = np.pi / (2)
        _ = brentq(self._eq, left, right - margin, args=(a))
        for i in range(1, Nroots+1):
            left = (2*i - 1)*np.pi/(2)
            right = (2*i + 1)*np.pi/(2)
            rts[i-1] = brentq(self._eq, left + margin, right - margin, args=(a))
    
        return rts    

    def calc_solution(self):
        """
        Función que evalúa la solución dadas las condiciones de un paso de tiempo

        Returns
        -------
        sol : List
            DESCRIPTION.

        """
        theta = (self.t_in-self.t_min)/(self.t_max-self.t_min)
        init = (self.init-self.t_min)/(self.t_max-self.t_min)
        ############# Sol. Estacionaria
        # Definir constantes de la solución estacionaria
        k1 = np.longfloat(0.5 * (self.kappa * self.Pe - np.sqrt(self.kappa**2 * self.Pe**2 + 4 * self.Pe * self.St)))
        k2 = np.longfloat(0.5 * (self.kappa * self.Pe + np.sqrt(self.kappa**2 * self.Pe**2 + 4 * self.Pe * self.St)))
        C2 = theta * k1 * np.exp(k1) / (k1*np.exp(k1) - k2*np.exp(k2))
        C1 = theta - C2
        # Solución estacionaria
        Mx = lambda x : C1*np.exp(k1*x) + C2*np.exp(k2*x)
    
        ############# Sol. Transiente        
        # Calcular autovalores
        lbd = self.solve_eq(200, self.a)
        # Definir la functión Kernel
        fn = np.sqrt(2) * np.sqrt((lbd**2 + self.a**2)/(lbd**2 + self.a**2 + self.a))
        Knx = lambda x : fn[:, None] * np.sin(lbd[:, None]*x)
        # Transformada integral de la solución inicial
        # 1, Interpolar datos de la condición inicial
        xint = np.linspace(0, 1, 200)
        t0_int = interp1d(self.xev, init, bounds_error=False, fill_value='extrapolate')(xint)
        phi0 = (t0_int - Mx(xint)) / np.exp(self.a*xint)
        phi0n = np.trapz(Knx(xint)*phi0, x=xint, axis=1)
        # 2, Solución del problema de autovalores
        phin = phi0n[:, None] * np.exp(-lbd[:, None]**2 * self.tau / self.Pe)
        # 3, Solución del problema transiente
        Nxt = np.exp(self.a*self.xev[:, None] + self.b*self.tau) * (np.sum(phin * Knx(self.xev), axis=0)[:, None])
    
        ############# Sol.
        sol = Mx(self.xev)[:, None] + Nxt
    
        return sol
    
    def update_temperature_profile(self, T_in, mass_flow, initial_profile):
        """
        Updates the temperature profile of the TES for the given time.

        Parameters
        ----------
        dt : TYPE
            Time step.
        mass_flow : Float
            Inlet mass flow [kg/s].
        T_in : Float
            Inlet Temperature [°C].

        Returns
        -------
        None.

        """
        
        self.init = initial_profile
        self.t_max = max(self.profile.max(), T_in)
        self.t_min = min(self.profile.min(), T_in)
        self.eq_params(T_in, mass_flow)
        self.profile = self.calc_solution().reshape((len(self.xev), ))*(self.t_max-self.t_min) + self.t_min
        self.init = self.profile
        self.tout = self.profile[-1]
        return self.profile

    def set_state(self, new_state):
        """
        Sets the operational state of the TES and switches the inlet and outlet if changing from charge to discharge and vice versa.
        :param new_state: str, the new state of the TES ('charge', 'discharge', 'standby').
        """
        
        if new_state != self.state and (new_state in ['charge', 'discharge']):
            # Switch inlet and outlet when changing between charge and discharge
            self.inlet, self.outlet = self.outlet, self.inlet
            self.profile = np.flip(self.profile)
        self.state = new_state

    def calculate_SoC(self, profile):
        """
        Calculate the energy stored in a TES unit by integrating the temperature profile.
        
        :param tes_temps: List of temperatures from each TES unit
        :return: List of energy stored in each TES unit
        """

        self.air_params()
        
        radius = self.Dint / 2
        volume = np.pi * (radius ** 2) * self.HT

        Cp_pb = self.cp_s * self.e + self.cp_f * (1-self.e)# (kJ/kg°C)
        rho_pb = self.rho_s * self.e + self.rho_out * (1-self.e)  #  (kg/m³)
        
        SoC = 0
        for temp in profile:
            energy = volume * rho_pb * Cp_pb  * temp / len(profile)
            SoC += energy #J
        return SoC/3.6e6 #kWh
         
class SolarThermalSystem:
    """
    The SolarThermalSystem class encapsulates a steady-state TESPy network with:
      - A compressor (for circulating CO2 at high pressure)
      - A ParabolicTrough collector (using TESPy's built-in class)
      - A simple HeatExchanger for process demand

    It is designed for parametric/time-step analyses in which you can vary
    the DNI (irradiance) at each solve. 
    """

    def __init__(self, rows=1, modules=1, 
                 tes_params=None, 
                 component_params = None, 
                 conexion_params=None,
                 HTF=None):
        """
        Constructor initializes placeholders for the network, components, 
        and connections. Actual creation of these will occur in other methods.
        """
        self.HTF = HTF
        self.rows = rows
        self.modules = modules
        
        self.tes_params = tes_params
        self.TES_dt = 3600
        
        self.component_params = component_params 
        self.conexion_params = conexion_params
        self.network = None
        self.compressor = None
        self.ptc_field = None
        self.process_hx = None
        self.cycle_closer = None
        self.discharge_hx = None 

        self.conn_comp_to_ptc = None
        self.conn_ptc_to_hx = None
        self.conn_hx_to_cc = None
        self.conn_cc_to_comp = None
        self.conn_pump_to_dhx = None
        self.conn_dhx_to_ph = None

        self.results = {}
        self.tes = ThermalEnergyStorage(self.tes_params, name='TES', dt=self.TES_dt)
        
    def create_network1(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')

        # 3) Create and add components
        self.comp = tpc.Compressor(label='Compressor_main')
        self.comp2 = tpc.Compressor(label='Compressor_Ch_loop')
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        self.ptc_field = tpc.ParabolicTrough(label='PTCField')

        # TES layout
        self.charge_tes_hx = tpc.HeatExchanger(label='Charge_TES_HX')
        
        self.splitter1 = tpc.nodes.splitter.Splitter(label='Splitter1')
        self.merge2 = tpc.nodes.merge.Merge(label='Merge2')
        
        #TES
        self.tes_ch_source = tpc.Source('TES_charge_inlet_source')
        self.tes_ch_sink   = tpc.Sink('TES_charge_outlet_sink')
        
        # Main Loop
        self.conn_1 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.ptc_field, 'in1',
            label='CC_PTC'
            )
        
        self.conn_2 = tpcn.Connection(
            self.ptc_field, 'out1',
            self.splitter1, 'in1',
            label='PTC_SP1'
            )
        
        self.conn_4 = tpcn.Connection(
            self.splitter1, 'out1',
            self.preheater_hx, 'in1',
            label='SP1_PH'
            )
        
        self.conn_5 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='PH_PR'
            )
        
        self.conn_6 = tpcn.Connection(
            self.process_hx, 'out1',
            self.comp, 'in1',
            label='PR_CP'
            )

        self.conn_7 = tpcn.Connection(
            self.comp, 'out1',
            self.merge2, 'in1',
            label='CP_MG2'
            )
        
        self.conn_9 = tpcn.Connection(
            self.merge2, 'out1',
            self.cycle_closer, 'in1',
            label='MG2_CC'
            )
        
        # Branch 1 (Charge path)
        self.conn_10 = tpcn.Connection(
            self.splitter1, 'out2',
            self.comp2, 'in1',
            label='SP1_CP2'
            )
        self.conn_20 = tpcn.Connection(
            self.comp2, 'out1',
            self.charge_tes_hx, 'in1',
            label='CP2_CHX'
            )
        self.conn_11 = tpcn.Connection(
            self.charge_tes_hx, 'out1',
            self.merge2, 'in2',
            label='CHX_MG2'
            )
        #TES

        self.conn_15 = tpcn.Connection(
            self.tes_ch_source, 'out1',
            self.charge_tes_hx, 'in2',
            label='CHSC_CHX'
            )
        
        self.conn_16   = tpcn.Connection(
            self.charge_tes_hx, 'out2',
            self.tes_ch_sink, 'in1',       
            label='CHX_CHSK')

        self.network.add_conns(
            self.conn_1,
            self.conn_2,
            self.conn_4,
            self.conn_5,
            self.conn_6,
            self.conn_7,
            self.conn_9,
            self.conn_10,
            self.conn_11,
            self.conn_15,
            self.conn_16,
            self.conn_20,
           )
    
        self.comp.set_attr(eta_s=self.component_params['comp_eta_s'])
        self.comp2.set_attr(eta_s=self.component_params['comp_eta_s'])

        #    Set collector parameters pero row (area, pr, DNI, design, etc.)
        self.ptc_field.set_attr(pr=self.component_params['ptc_pr'], 
                                aoi=self.component_params['ptc_aoi'], 
                                doc=self.component_params['ptc_doc'],
                                Tamb=self.component_params['ptc_tamb'], 
                                A=self.component_params['ptc_A'], 
                                eta_opt=self.component_params['eta_opt'], 
                                c_1=self.component_params['ptc_c_1'], 
                                c_2=self.component_params['ptc_c_2'], 
                                E=self.component_params['ptc_E'],
                                iam_1=self.component_params['ptc_iam_1'], 
                                iam_2=self.component_params['ptc_iam_2'])


        # Outflow of process HX
        self.conn_6.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        self.process_hx.set_attr(pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # TES HTF
        self.conn_15.set_attr(p=self.conexion_params['15_p'], 
                              fluid=self.conexion_params['15_f'])

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_5.set_attr(T=self.conexion_params['5_T'])
        
    def create_network2(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')

        # 3) Create and add components
        self.comp = tpc.Compressor(label='Compressor_main')
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        self.ptc_field = tpc.ParabolicTrough(label='PTCField')
        
        # Main Loop
        self.conn_1 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.ptc_field, 'in1',
            label='CC_PTC'
            )
        
        self.conn_4 = tpcn.Connection(
            self.ptc_field, 'out1',
            self.preheater_hx, 'in1',
            label='PTC_PH'
            )
        
        self.conn_5 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='PH_PR'
            )
        
        self.conn_6 = tpcn.Connection(
            self.process_hx, 'out1',
            self.comp, 'in1',
            label='PR_CP'
            )

        self.conn_7 = tpcn.Connection(
            self.comp, 'out1',
            self.cycle_closer, 'in1',
            label='CP_CC'
            )

        self.network.add_conns(
            self.conn_1,
            self.conn_4,
            self.conn_5,
            self.conn_6,
            self.conn_7,
           )
        
        self.comp.set_attr(eta_s=self.component_params['comp_eta_s'])

        #    Set collector parameters pero row (area, pr, DNI, design, etc.)
        self.ptc_field.set_attr(pr=self.component_params['ptc_pr'], 
                                aoi=self.component_params['ptc_aoi'], 
                                doc=self.component_params['ptc_doc'],
                                Tamb=self.component_params['ptc_tamb'], 
                                A=self.component_params['ptc_A'], 
                                eta_opt=self.component_params['eta_opt'], 
                                c_1=self.component_params['ptc_c_1'], 
                                c_2=self.component_params['ptc_c_2'], 
                                E=self.component_params['ptc_E'],
                                iam_1=self.component_params['ptc_iam_1'], 
                                iam_2=self.component_params['ptc_iam_2'])


        # Outflow of process HX
        self.conn_6.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        self.process_hx.set_attr(pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_5.set_attr(T=self.conexion_params['5_T'])

    def create_network3(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """
        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')

        # 3) Create and add components
        self.comp = tpc.Compressor(label='Compressor_main')
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
    
        # TES layout
        self.discharge_tes_hx = tpc.HeatExchanger(label='Discharge_TES_HX')
        
        #TES
        self.tes_dch_source = tpc.Source('TES_discharge_inlet_source')
        self.tes_dch_sink   = tpc.Sink('TES_discharge_outlet_sink')
        # Main Loop

        self.conn_4 = tpcn.Connection(
            self.discharge_tes_hx, 'out2',
            self.preheater_hx, 'in1',
            label='DHX_PH'
            )
        
        self.conn_5 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='PH_PR'
            )
        
        self.conn_6 = tpcn.Connection(
            self.process_hx, 'out1',
            self.comp, 'in1',
            label='PR_CP'
            )

        self.conn_7 = tpcn.Connection(
            self.comp, 'out1',
            self.cycle_closer, 'in1',
            label='CP_CC'
            )

        # Branch 2 (Discharge path)
        self.conn_12 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.discharge_tes_hx, 'in2',
            label='CC_DHX'
            )
        
        #TES        
        self.conn_17= tpcn.Connection(
            self.tes_dch_source, 'out1',       
            self.discharge_tes_hx, 'in1',       
            label='DCHSC_DHX'
            )
        
        self.conn_18  = tpcn.Connection(
            self.discharge_tes_hx, 'out1',
            self.tes_dch_sink, 'in1',
            label='DHX_DCHSK'
            )

        self.network.add_conns(

            self.conn_4,
            self.conn_5,
            self.conn_6,
            self.conn_7,
            self.conn_12,
            self.conn_17,
            self.conn_18,
           )

        self.comp.set_attr(eta_s=self.component_params['comp_eta_s'])

        # Outflow of process HX
        self.conn_6.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        self.process_hx.set_attr(pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # TES HTF
        self.conn_17.set_attr(p=self.conexion_params['17_p'], 
                              fluid=self.conexion_params['17_f'])

        # Preheater HX
        #system.preheater_hx.set_attr(pr1=0.99, pr2=0.99)
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_5.set_attr(T=self.conexion_params['5_T'])
        
    def create_network4(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')

        # 3) Create and add components
        self.comp = tpc.Compressor(label='Compressor_main')
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        
        # Main Loop
        self.conn_1 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.preheater_hx, 'in1',
            label='CC_PH'
            )
        

        self.conn_5 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='PH_PR'
            )
        
        self.conn_6 = tpcn.Connection(
            self.process_hx, 'out1',
            self.comp, 'in1',
            label='PR_CP'
            )

        self.conn_7 = tpcn.Connection(
            self.comp, 'out1',
            self.cycle_closer, 'in1',
            label='CP_CC'
            )
        
        self.network.add_conns(
            self.conn_1,
            self.conn_5,
            self.conn_6,
            self.conn_7,
           )
        
        self.comp.set_attr(eta_s=self.component_params['comp_eta_s'])

        #    Set collector parameters pero row (area, pr, DNI, design, etc.)

        # Outflow of process HX
        self.conn_6.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        self.process_hx.set_attr(pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_5.set_attr(T=self.conexion_params['5_T'])
        

    def set_operation_mode(self, TESmode='4', current_irr=0):
        """
        mode 1: High iradiation, PTC to process and to TES
        mode 2: Mid iradiation, PTC to process, TES in standby
        mode 3: Low irradiation, TES to process
        mode 4: Low irradiation, TES in standby
        """
        if TESmode == '1':
            self.create_network1()
            # Calculate heat flow to deliver to TES
            Q_ptc_max = 600*self.ptc_field.A.val*0.7
            Q_ptc_now = current_irr*self.ptc_field.A.val*0.7
            Q_tes = Q_ptc_now - Q_ptc_max
            if Q_tes < Q_ptc_max * 0.1:
                self.create_network2()
            else:
            # Divide flow between Process and TES
                
                self.conn_2.set_attr(T=None, m=None)
                #self.conn_4.set_attr(m=tpcn.Ref(self.conn_11, 5, 0))
                self.conn_11.set_attr(T=self.conexion_params['6_T'], m=None)
                self.conn_15.set_attr(m=tpcn.Ref(self.conn_11, 2, 0))
                
                self.tes.set_state('charge')
            
                self.charge_tes_hx.set_attr(Q=-Q_tes, pr1=0.99, pr2=0.99)
        elif TESmode == '2':
            # All flow from PTC to process
            self.create_network2()

        elif TESmode == '3':
            # All flow from TES, none in PTC and charge loop
            self.create_network3()
            self.conn_4.set_attr(T=self.conexion_params['6_T']+20, m=None)
            self.discharge_tes_hx.set_attr(Q=None, pr1=0.99, pr2=0.99, eff_max=None)
            self.conn_17.set_attr(m=tpcn.Ref(self.conn_4, 1, 0))
            
            self.tes.set_state('discharge')
        elif TESmode == '4':
            self.create_network4()
        else:
            raise ValueError(f"Unknown mode {TESmode}, use 'charge' or 'discharge'.")

            
    def solve_network(self, mode='design', design_path="base_design", TESmode='1'):
        """
        Attempts to solve the network in the specified mode (default: 'design').
        Raises an exception if the solver fails.
        
        Args:
            mode (str): 'design' or 'offdesign' (TESPy modes).
        """

        name = f'base_design_{TESmode}'        
        if mode == 'design':
            
            self.network.solve(mode=mode)
            self.network.save(name)
        else:
            self.network.solve(mode=mode, design_path = f'base_design_{TESmode}')
            if not self.network.converged:
                raise RuntimeError("TESPy solver did not converge.")

class Solver:
    """
    Runs a quasi-steady simulation of the SolarThermalSystem over time-series data.
    """
    def __init__(self, solar_thermal_system, file_path=None):
        self.solar_system = solar_thermal_system
        self.results = []
        self.current_mode = '4' 
        self.file_path = file_path

    def load_data(self, csv, start_date, days_to_simulate):
        """
        Loads external data from a CSV file and fixes the year for all timestamps.
        :return: DataFrame, data loaded and adjusted.
        """
        fixed_year = 2022        

        # 2) Read TMY
        tmy_data = pd.read_csv('TMY.csv')#, parse_dates=['Fecha/Hora'])

        # Filter out data for 'days_to_simulate' from the start
        #start_date = tmy_data['Fecha/Hora'].min()
        #end_date   = start_date + pd.Timedelta(days=days_to_simulate)
        #filtered_data = tmy_data[(tmy_data['Fecha/Hora'] >= start_date) & (tmy_data['Fecha/Hora'] < end_date)]
        
        
        # Fix the year for all timestamps
        tmy_data['Fecha/Hora'] = pd.to_datetime(tmy_data['Fecha/Hora'])
        tmy_data['Fecha/Hora'] = tmy_data['Fecha/Hora'].apply(lambda x: x.replace(year=fixed_year))
        start_date = tmy_data['Fecha/Hora'].min()
        end_date   = start_date + pd.Timedelta(days=days_to_simulate)
        print(start_date, end_date)
       
        #filtered_data = filtered_data[filtered_data['Fecha/Hora'] >= start_date]
        filtered_data = tmy_data[(tmy_data['Fecha/Hora'] >= start_date) & (tmy_data['Fecha/Hora'] < end_date)]
        return filtered_data

    def gen_latex(self, path='report', filename='report.tex'):
        ttdm.document_model(self.solar_system.network)

    def get_mode(self, irr, TES_Tout):
        if irr > 600:
            if self.solar_system.conexion_params['6_T'] > TES_Tout-20:
                return '1'
            else: 
                return '2'
        elif irr > 200:
            return '2'
        else:
            if self.solar_system.conexion_params['6_T'] > TES_Tout - 10:
                return '4'
            else:
                return '3'
    
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

    # -------------------------------------------------------------------------
    # 2) Coupling Iteration Between TES and Main Loop (steady or single time-step)
    # -------------------------------------------------------------------------
    def _iterate_tes_coupling(self, system,
                              mode='design', TESmode='2', 
                              design_path='base_design'):
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

        # 1) Set the operation mode (ensures correct flow splits)
        #system.set_operation_mode(TESmode, irr=current_irr)

        # 2) Initialize the TES_HX source temperature from top/bottom
        if TESmode == '1':
            T_in_bot = system.tes.profile[-1]  # top node for charging
            system.conn_15.set_attr(T=T_in_bot)
        elif TESmode == '3': # discharging: use bottom node to extract heat from the hottest (bottom) region
            T_in_bot = system.tes.profile[-1]
            system.conn_17.set_attr(T=T_in_bot)
        old_profile = system.tes.profile
        # 3) Iteration loop
        for iteration in range(max_iter):
            # a) Solve the main TESPy network
            if mode == 'offdesign':
                self.solar_system.network.set_attr(iterinfo=False)
            system.solve_network(mode=mode, design_path=design_path, TESmode=TESmode)
            if not system.network.converged:
                #self.gen_latex()
                print(f"[WARNING] TESPy solver did not converge at iteration {iteration+1}.")
                break
            if TESmode in ['2', '4']:
                status = 'converged'
                self.TES_profiles.append(system.tes.profile.tolist())
                break
            # b) Read new TES inlet conditions from TES_HX outlet
            if TESmode == '1':
                T_tes_in = system.conn_16.T.val
                m_tes_in = system.conn_16.m.val_SI
            elif TESmode == '3':  # discharging: use bottom node to extract heat from the hottest (bottom) region
                T_tes_in = system.conn_18.T.val
                m_tes_in = system.conn_18.m.val_SI

            system.tes.update_temperature_profile(
                T_in=T_tes_in,
                mass_flow=m_tes_in,
                initial_profile=old_profile
            )

            T_tes_out = system.tes.tout
            # d) Set the new outlet temperature to the HX inlet for next iteration
            if TESmode == '1':
                system.conn_15.set_attr(T=T_tes_out)
            elif TESmode == '3':
                system.conn_17.set_attr(T=T_tes_out)

            # e) Track T_out for our multi-step convergence logic
            T_out_history.append(T_tes_out)
            if len(T_out_history) > 1:
                prev_T = T_out_history[-2]
                if abs(prev_T) > 1e-6:
                    cf = abs(T_tes_out - prev_T) / abs(prev_T)
                else:
                    cf = 0.0
                conv_factors.append(cf)

            # f) Evaluate our custom convergence criteria
            status = self._check_tes_convergence(T_out_history, conv_factors)
            if status == 'converged':
                old_profile = system.tes.profile
                self.TES_profiles.append(system.tes.profile.tolist())
                #print(f"[INFO] TES iteration converged in {iteration+1} steps (steady).")

                break
            elif status == 'diverged':
                
                print(f"[WARNING] TES iteration diverging at iteration {iteration+1}!")
                break

        else:
            # If we never hit a 'break', we didn't converge within max_iter
            print("[WARNING] Reached max iteration count without TES convergence.")

    # -------------------------------------------------------------------------
    # 3) Steady-State Solver
    # -------------------------------------------------------------------------
    def solve_network_steady(self, mode='design', TESmode='2', 
                             design_path="base_design", current_irr=0):
        """
        Public method to solve the system in a stationary (steady) mode,
        including iteration with the TES if present.

        Args:
            operation_mode (str): 'charge' or 'discharge'.
            design_path (str): path to the saved design data (for offdesign mode).
        """
        # Simply call our coupling iteration for one single "steady" step
        system = self.solar_system
        TESmode = self.get_mode(current_irr, self.solar_system.tes.profile[-1])
        print(f'TES mode {TESmode}')
        self.solar_system.set_operation_mode(TESmode=TESmode, current_irr=current_irr)
        self._iterate_tes_coupling(mode=mode, system = system,
                                   TESmode=TESmode, design_path=design_path)

    def run_quasi_steady_simulation(self, days_to_simulate = 10,
                                    csv = 'TMY.csv', time_col='Fecha/Hora',
                                    E_col='dni', Tamb_col='temp'):
        """
        Existing method: only the snippet showing how to call _iterate_tes_coupling now.
        """
        system = self.solar_system
        self.solar_system.create_network4()
        self.results = []

        data_frame = self.load_data(csv, '2022-01-01', days_to_simulate=days_to_simulate)
        # Track total runtime
        print("\n=== Starting transient simulation ===")
        start_time = time.time()


        for idx, row in tqdm(data_frame.iterrows(), total=len(data_frame), desc="Simulating"):
            current_irr = row[E_col]
            current_Tamb = row[Tamb_col]
            
            # Decide TES mode
            new_TESmode = self.get_mode(current_irr, self.solar_system.tes.profile[-1])
            if new_TESmode != self.current_mode:
                self.solar_system.set_operation_mode(TESmode=new_TESmode, current_irr=current_irr)
                self.current_mode = new_TESmode

            # Set PTC/Discharge boundary conditions
            if self.current_mode in ['1','2']:
                self.solar_system.ptc_field.set_attr(E=current_irr, Tamb=current_Tamb)

            design_path = f'base_design_{self.current_mode}'
            
            # For each time step, do the same iteration
            self._iterate_tes_coupling(mode='offdesign', system = system,
                                       TESmode=self.current_mode, design_path=design_path) 
            
            #print('Time step: ', idx)
            #print('TES mode: ', self.current_mode)
            
            #print('TES profile: ', self.TES_profiles)

            # After final iteration for this time-step:
            if self.current_mode in ['1','2']:
                Q_ptc_kJ   = self.solar_system.ptc_field.Q.val * 3600.0
            else:
                Q_ptc_kJ   = 0
            Q_ph_kJ    = self.solar_system.preheater_hx.Q.val * 3600.0
            comp_power = self.solar_system.comp.P.val
            #print('Q PTC: ', Q_ptc_kJ/1000000000)
            self.results.append({
                'time': row[time_col],
                'E': current_irr,
                'Tamb': current_Tamb,
                'ptc_energy_kJ': Q_ptc_kJ,
                'ph_energy_kJ':  Q_ph_kJ,
                'comp_power_W':  comp_power,
                # Optionally store final TES temps:
                #'T_tes_in':  self.solar_system.conn_teshx_to_tes_sink.T.val,
                #'T_tes_out': self.solar_system.conn_tes_source_to_teshx.T.val,
                'TES_profiles': self.TES_profiles,
                'TES_layout': self.solar_system.tes.state
            })

        # End of simulation: print total elapsed time
        end_time = time.time()
        total_runtime = end_time - start_time
        print(f"\nTransient simulation completed in {total_runtime:.2f} seconds.")

        return self.results

    def compute_performance_metrics(self):
        """
        Process self.results to compute plant factor, pump energy consumption, etc.

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
        total_ph_energy_kJ  = df['ph_energy_kJ'].sum()
        # Pump power (W) * 3600 s for each step (assuming dt=1h). If dt != 1h, adjust accordingly.
        # Here we multiply by dt_hours each iteration's power. For simplicity, we assume dt=1, 
        # or you can do a row-by-row integral if dt varies.
        total_comp_energy_kJ = (df['comp_power_W'] * 3600.0 * self.dt_hours).sum()
        
        # Convert kJ to MWh (1 MWh = 3.6e6 kJ)
        ptc_energy_MWh   = total_ptc_energy_kJ / 3.6e6
        ph_energy_MWh    = total_ph_energy_kJ  / 3.6e6
        comp_energy_MWh  = total_comp_energy_kJ / 3.6e6
        
        # Optional "solar plant factor" if user provided a process demand
        spf = total_ptc_energy_kJ / (total_ptc_energy_kJ + total_ph_energy_kJ) # fraction

        # Print performance summary line by line
        print("\n=== Performance Summary ===")
        print(f"Total PTC Energy:       {ptc_energy_MWh:6.2f} MWh")
        print(f"Total Preheater Energy:{ph_energy_MWh:6.2f} MWh")
        print(f"Total Compressor Energy:      {comp_energy_MWh:6.2f} MWh")
        if spf is not None:
            print(f"Solar Plant Factor:     {spf * 100:6.2f}%")
        print("================================\n")

        return self.results
class Reporting:
    """
    A class responsible for plotting and reporting simulation results.
    """
    
    def plot_results(self, df_results):
        """
        Plots the main simulation results over time.

        Parameters
        ----------
        df_results : pd.DataFrame
            A DataFrame that must have 'time', 'ptc_energy_kJ', and 'gb_energy_kJ' columns
            (or whichever columns you need for plotting).
        """
        plt.figure(figsize=(8, 5))
        plt.plot(df_results['time'], df_results['ptc_energy_kJ'], label='PTC Energy [kJ]')
        plt.plot(df_results['time'], df_results['ph_energy_kJ'],  label='Preheater Energy [kJ]')
        plt.xlabel('Time')
        plt.ylabel('Energy [kJ]')
        plt.title('PTC and Preheater Energy vs. Time')
        plt.legend()
        plt.tight_layout()
        plt.show()
        
    def plot_TES_profile_colormap(self, df_results):
        """
        Plots a 2D colormap of the TES temperature profiles over time.
    
        Parameters
        ----------
        df_results : pd.DataFrame
            Must have:
            - 'time': (numeric or datetime) time or time-step index
            - 'TES_profiles': each entry is the 1D temperature array (or something convertible to 1D)
                              for that time-step in the TES.
        """
        # 1) Extract the list of TES profiles
        profiles_list = df_results['TES_profiles'].values  # an array/list of arrays
        N = len(profiles_list)  # number of time steps
    
        # 2) Convert each profile to a 1D numpy array (flatten if needed),
        #    and find the length N (assumed same for all rows).
        #    If your data is strictly 1D per step, you can just do:
        #      N = len(profiles_list[0])
        #    If some are 2D or nested, flatten them:
        first_profile = np.array(profiles_list[0]).ravel()
        M = len(first_profile)
    
        # 3) Build the 2D array Z with shape (M, N)
        Z = np.zeros((M, N))
        for i in range(N):
            # Convert to numpy array and flatten in case it's 2D (e.g. shape (N,1))
            list_element = profiles_list[i]
            list_element2 = list_element[0][::-1]
            if df_results['TES_layout'][i] =='discharge':
                temp_profile = np.array(list_element).ravel()
            elif df_results['TES_layout'][i] == 'charge':
                temp_profile = np.array(list_element2).ravel()

            # Optional: sanity check that all profiles have same length
            if len(temp_profile) != M:
                raise ValueError(
                    f"Row {i} in TES_profiles has length {len(temp_profile)}, "
                    f"but expected {M}."
                )
            Z[:,i] = temp_profile
    
        # 4) Create an x-axis for TES dimension. 
        #    If you have actual tank length in meters, use e.g. np.linspace(0, L, N)
        y = np.linspace(0, 1, M)  # normalized from 0..1
    
        # 5) Convert 'time' to numeric axis
        times_raw = df_results['time'].values
        # If 'time' is datetime, convert to hours from the first timestamp
        if isinstance(times_raw[0], pd.Timestamp):
            t0 = df_results['time'].iloc[0]
            x_vals = (df_results['time'] - t0).dt.total_seconds() / 3600.0
            x_label = 'Time [h]'
        else:
            # Use raw numeric values or indices
            x_vals = times_raw
            x_label = 'Time'
    
        # 6) Make grids for pcolormesh
        X, Y = np.meshgrid(x_vals, y)
    
        # 7) Plot with pcolormesh
        fig, ax = plt.subplots(figsize=(8, 5))
        # shading='auto' is recommended (avoids some edge alignment issues)
        cs = ax.pcolormesh(X, Y, Z, cmap='coolwarm', shading='auto')
        
        # 8) Add a colorbar
        cbar = plt.colorbar(cs, ax=ax)
        cbar.set_label('Temperature [°C]', rotation=90)
    
        # 9) Labels, title, etc.
        ax.set_ylabel('Normalized TES Height [-]')
        ax.set_xlabel(x_label)
        ax.set_title('TES Temperature Distribution vs. Time')
    
        plt.tight_layout()
        plt.show()