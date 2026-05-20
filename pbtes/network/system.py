import tespy.networks as tpn
import tespy.connections as tpcn
import tespy.components as tpc
from pbtes.storage import ThermalEnergyStorage


class SolarThermalSystem:
    """
    The SolarThermalSystem class encapsulates a steady-state TESPy network with:
      - A Pump (for circulating CO2 at high pressure)
      - A ParabolicTrough collector (using TESPy's built-in class)
      - A simple HeatExchanger for process demand

    It is designed for parametric/time-step analyses in which you can vary
    the DNI (irradiance) at each solve. 
    """

    def __init__(self, rows=1, modules=1, 
                 tes_params=None, 
                 component_params = None, 
                 conexion_params=None,
                 HTF=None,
                 topology='Parallel',
                 tank_config='indirect'):
        """
        Constructor initializes placeholders for the network, components, 
        and connections. Actual creation of these will occur in other methods.
        """
        self.HTF = HTF
        self.topology = topology
        self.tank_config = tank_config  # 'direct' or 'indirect'
        self.rows = rows
        self.modules = modules
        
        self.tes_params = tes_params
        self.TES_dt = 3600
        
        self.component_params = component_params 
        self.conexion_params = conexion_params
        self.network = None
        self.pump = None
        self.ptc_field = None
        self.process_hx = None
        self.cycle_closer = None
        self.discharge_hx = None 

        self.conn_pump_to_ptc = None
        self.conn_ptc_to_hx = None
        self.conn_hx_to_cc = None
        self.conn_cc_to_pump = None
        self.conn_pump_to_dhx = None
        self.conn_dhx_to_ph = None

        self.results = {}
        self.tes = ThermalEnergyStorage(self.tes_params, name='TES', dt=self.TES_dt)
        
        self.ptc_field_A = self.component_params['ptc_A']

        self._zinc_pool_T06 = None


    def create_network(self, mode: int, design_mode: str = 'design'):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        
        In 'design' mode: all component parameters (Q, ttd, A, E, T, pr) are set.
        In 'offdesign' mode: only structural parameters (p, fluid, pr) are set;
                             thermal parameters come from stored design.
        """
        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        self.network.set_attr(T_range=[300, 600])

        # 3) Create and add components
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        from pbtes.components import PTCField
        self.ptc_field = PTCField(label='PTCField', rows=self.rows, modules=self.modules)

        if mode in [1, 5, 6]:
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.charge_tes_hx = tpc.HeatExchanger(label='Charge_TES_HX')
            else:
                self.charge_tes_hx = tpc.SimpleHeatExchanger(label='Charge_TES_Pipe')
            if mode == 1 and getattr(self, 'topology', 'Parallel') == 'Parallel':
                self.splitter1 = tpc.nodes.splitter.Splitter(label='Splitter1')
                self.merge2 = tpc.nodes.merge.Merge(label='Merge2')
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.tes_ch_source = tpc.Source('TES_charge_inlet_source')
                self.tes_ch_sink   = tpc.Sink('TES_charge_outlet_sink')
        elif mode == 3:
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.discharge_tes_hx = tpc.HeatExchanger(label='Discharge_TES_HX')
                self.tes_dch_source = tpc.Source('TES_discharge_inlet_source')
                self.tes_dch_sink   = tpc.Sink('TES_discharge_outlet_sink')
            else:
                self.discharge_tes_hx = tpc.SimpleHeatExchanger(label='Discharge_TES_Pipe')
        
        # Mode-specific connections
        if mode == 1:
            self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
            if getattr(self, 'topology', 'Parallel') == 'Series':
                self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.preheater_hx, 'in1', label='02_PTC_PH')
                self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
                self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.charge_tes_hx, 'in1', label='06_PR_CHX')
                self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.cycle_closer, 'in1', label='10_CHX_CC')
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                    self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10, self.conn_13, self.conn_14)
                    for conn in [self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10, self.conn_13, self.conn_14]:
                        conn.set_attr(T0=500, h0=700, m0=5, p0=5)
                else:
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10)
                    for conn in [self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10]:
                        conn.set_attr(T0=500, h0=700, m0=5, p0=5)
            else:
                self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.splitter1, 'in1', label='02_PTC_SP1')
                self.conn_04 = tpcn.Connection(self.splitter1, 'out1', self.preheater_hx, 'in1', label='04_SP1_PH')
                self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
                self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.merge2, 'in1', label='06_PR_MG2')
                self.conn_08 = tpcn.Connection(self.merge2, 'out1', self.cycle_closer, 'in1', label='08_MG2_CC')
                self.conn_09 = tpcn.Connection(self.splitter1, 'out2', self.charge_tes_hx, 'in1', label='09_SP1_CHX')
                self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.merge2, 'in2', label='10_CHX_MG2')
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                    self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_04, self.conn_05, self.conn_06, self.conn_08, self.conn_09, self.conn_10, self.conn_13, self.conn_14)
                    for conn in [self.conn_01, self.conn_02, self.conn_04, self.conn_05, self.conn_06, self.conn_08, self.conn_09, self.conn_10, self.conn_13, self.conn_14]:
                        conn.set_attr(T0=500, h0=700, m0=5, p0=5)
                else:
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_04, self.conn_05, self.conn_06, self.conn_08, self.conn_09, self.conn_10)
                    for conn in [self.conn_01, self.conn_02, self.conn_04, self.conn_05, self.conn_06, self.conn_08, self.conn_09, self.conn_10]:
                        conn.set_attr(T0=500, h0=700, m0=5, p0=5)
        elif mode == 2:
            self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
            self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.preheater_hx, 'in1', label='02_PTC_PH')
            self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
            self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer, 'in1', label='06_PR_CC')
            self.network.add_conns(self.conn_01, self.conn_02, self.conn_05, self.conn_06)
            for conn in [self.conn_01, self.conn_02, self.conn_05, self.conn_06]:
                conn.set_attr(T0=500, h0=714, m0=35, p0=5)
        elif mode == 3:
            self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
            self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer, 'in1', label='06_PR_CC')
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.conn_04 = tpcn.Connection(self.discharge_tes_hx, 'out2', self.preheater_hx, 'in1', label='04_DHX_PH')
                self.conn_11 = tpcn.Connection(self.cycle_closer, 'out1', self.discharge_tes_hx, 'in2', label='11_CC_DHX')
                self.conn_15 = tpcn.Connection(self.tes_dch_source, 'out1', self.discharge_tes_hx, 'in1', label='15_DCHSC_DHX')
                self.conn_16 = tpcn.Connection(self.discharge_tes_hx, 'out1', self.tes_dch_sink, 'in1', label='16_DHX_DCHSK')
                self.network.add_conns(self.conn_04, self.conn_05, self.conn_06, self.conn_11, self.conn_15, self.conn_16)
                for conn in [self.conn_04, self.conn_05, self.conn_06, self.conn_11, self.conn_15, self.conn_16]:
                    conn.set_attr(T0=520, h0=700, m0=30, p0=5)
                self.discharge_tes_hx.set_attr(pr1=1.0, pr2=1.0)
            else:
                self.conn_04 = tpcn.Connection(self.discharge_tes_hx, 'out1', self.preheater_hx, 'in1', label='04_DHX_PH')
                self.conn_11 = tpcn.Connection(self.cycle_closer, 'out1', self.discharge_tes_hx, 'in1', label='11_CC_DHX')
                self.network.add_conns(self.conn_04, self.conn_05, self.conn_06, self.conn_11)
                for conn in [self.conn_04, self.conn_05, self.conn_06, self.conn_11]:
                    conn.set_attr(T0=500, h0=714, m0=35, p0=5)
                self.discharge_tes_hx.set_attr(pr=1.0)

        elif mode == 4:
            self.conn_04 = tpcn.Connection(self.cycle_closer, 'out1', self.preheater_hx, 'in1', label='04_CC_PH')
            self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
            self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer, 'in1', label='06_PR_CC')
            self.network.add_conns(self.conn_04, self.conn_05, self.conn_06)
            for conn in [self.conn_04, self.conn_05, self.conn_06]:
                conn.set_attr(T0=500, h0=714, m0=35, p0=5)

        elif mode == 5:
            self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
            self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.charge_tes_hx, 'in1', label='02_PTC_CHX')
            self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.preheater_hx, 'in1', label='10_CHX_PH')
            self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
            self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer, 'in1', label='06_PR_CC')
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                self.network.add_conns(self.conn_01, self.conn_02, self.conn_10, self.conn_05, self.conn_06, self.conn_13, self.conn_14)
                for c in [self.conn_01,self.conn_02,self.conn_10,self.conn_05,self.conn_06,self.conn_13,self.conn_14]:
                    c.set_attr(T0=550, h0=700, m0=30, p0=5)
            else:
                self.network.add_conns(self.conn_01, self.conn_02, self.conn_10, self.conn_05, self.conn_06)
                for c in [self.conn_01,self.conn_02,self.conn_10,self.conn_05,self.conn_06]:
                    c.set_attr(T0=550, h0=700, m0=30, p0=5)

        elif mode == 6:
            if getattr(self, 'topology', 'Parallel') == 'Series':
                self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
                self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.preheater_hx, 'in1', label='02_PTC_PH_Series')
                self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR_Series')
                self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.charge_tes_hx, 'in1', label='06_PR_CHX_Series')
                self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.cycle_closer, 'in1', label='10_CHX_CC_Series')
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                    self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10, self.conn_13, self.conn_14)
                    for conn in [self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10, self.conn_13, self.conn_14]:
                        conn.set_attr(T0=500, h0=700, m0=2)
                else:
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10)
                    for conn in [self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10]:
                        conn.set_attr(T0=500, h0=700, m0=2)
            else:
                self.cycle_closer2 = tpc.CycleCloser(label='CycleCloser2')
                self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
                self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.charge_tes_hx, 'in1', label='02_PTC_CHX')
                self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.cycle_closer, 'in1', label='10_CHX_CC')
                self.conn_04 = tpcn.Connection(self.cycle_closer2, 'out1', self.preheater_hx, 'in1', label='04_CC2_PH')
                self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
                self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer2, 'in1', label='06_PR_CC2')
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                    self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                    conns = [self.conn_01, self.conn_02, self.conn_10, self.conn_04, self.conn_05, self.conn_06, self.conn_13, self.conn_14]
                else:
                    conns = [self.conn_01, self.conn_02, self.conn_10, self.conn_04, self.conn_05, self.conn_06]
                self.network.add_conns(*conns)
                for conn in conns: conn.set_attr(T0=500, h0=700, m0=5)
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_02.set_attr(p=self.conexion_params['6_p'], fluid=self.conexion_params['6_f'])
                    self.charge_tes_hx.set_attr(pr1=1.0, pr2=1.0)


        # === STRUCTURAL parameters (always applied, design + offdesign) ===
        
        
        # PTC pressure drop
        if mode in [1, 2, 5, 6]:
            self.ptc_field.set_attr(pr=1.0)
        
        # Secondary loop connection pressure and fluid (always)
        if mode in [1, 5, 6] and hasattr(self, 'conn_13'):
            self.conn_13.set_attr(p=self.conexion_params['13_p'], fluid=self.conexion_params['13_f'])
        if mode == 3 and hasattr(self, 'conn_15'):
            self.conn_15.set_attr(p=self.conexion_params['15_p'], fluid=self.conexion_params['15_f'])
        
        if hasattr(self, 'conn_06') and self.conn_06 is not None:
            self.conn_06.set_attr(
                p=self.conexion_params['6_p'],
                fluid=self.conexion_params['6_f']
            )
        
        if mode in [5, 6] and hasattr(self, 'conn_02') and self.conn_02 is not None:
            self.conn_02.set_attr(p=self.conexion_params['6_p'])
        
        # HX pressure drops (structural; skip for M6 Parallel - uses conn p anchors)
        is_m6_par = (mode == 6 and getattr(self, 'topology', 'Parallel') == 'Parallel')
        if mode in [1, 5, 6] and hasattr(self, 'charge_tes_hx'):
            if getattr(self, 'tank_config', 'indirect') == 'indirect' and not is_m6_par:
                self.charge_tes_hx.set_attr(pr2=1.0)
        
        # Process pressure drop (always, structural)
        self.process_hx.set_attr(pr=1.0)
        if getattr(self, 'topology', 'Parallel') == 'Series':
            self.preheater_hx.set_attr(pr=1.0)
        
        # === BOUNDARY CONDITIONS (always applied) ===
        if hasattr(self, 'conn_05') and self.conn_05 is not None:
            self.conn_05.set_attr(T=self.conexion_params['5_T'])
        if hasattr(self, 'conn_06') and self.conn_06 is not None and not is_m6_par:
            self.conn_06.set_attr(T=self.conexion_params['6_T'])
        if not is_m6_par:
            self.process_hx.set_attr(Q=self.component_params['PR_Q'])
        
        # === DESIGN-ONLY parameters (component sizing) ===
        if design_mode == 'design':            
            # PTC design parameters (skip M6 Par - independent cycle)
            if mode in [1, 5, 6] and not is_m6_par:
                self.ptc_field.set_attr(
                    aoi=self.component_params['ptc_aoi'], 
                    doc=self.component_params['ptc_doc'],
                    Tamb=self.component_params['ptc_tamb'], 
                    A=self.component_params['ptc_A'], 
                    eta_opt=self.component_params['eta_opt'], 
                    c_1=self.component_params['ptc_c_1'], 
                    c_2=self.component_params['ptc_c_2'], 
                    E=self.component_params['ptc_E'],
                    iam_1=self.component_params['ptc_iam_1'], 
                    iam_2=self.component_params['ptc_iam_2']
                )
            
            # HX thermal design parameter (force kA computation)
            if mode in [1, 5] and hasattr(self, 'charge_tes_hx'):
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.charge_tes_hx.set_attr(ttd_l=20)
            if mode == 3 and hasattr(self, 'discharge_tes_hx'):
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.discharge_tes_hx.set_attr(ttd_l=20)
        
        if mode in [2, 3, 4, 6]:
            pass

    def set_operation_mode(self, TESmode='4', 
                           current_irr=0,
                           profile=None,
                           prev_TES_lay = 'Charge',
                           mode = 'design'):
        """
        mode 1: High irradiation, PTC to process and to TES
        mode 2: Mid irradiation, PTC to process, TES in standby
        mode 3: Low irradiation, TES to process
        mode 4: Low irradiation, TES in standby (auxiliary heater supplies process)
        mode 6: Mid to high irradiation, PTC full to TES (auxiliary heater supplies process)
        """
        if prev_TES_lay == 'Charge':
            TES_top = profile[0]
            TES_bot = profile[-1]
        elif prev_TES_lay == 'Discharge':
            TES_top = profile[-1]
            TES_bot = profile[0]

        if TESmode == '1':
            self.create_network(mode=1, design_mode=mode)
            self.tes.set_state('charge')
            
            TES_bot = self.tes.profile[-1]
            
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.conn_14.set_attr(T=TES_bot + 40)  # 40K offset for CHX ttd_l=20 to have working DT
            
            self.preheater_hx.set_attr(Q=0)
            
            if mode == 'design':
                self.conn_05.set_attr(T=self.conexion_params['5_T'])
                self.conn_06.set_attr(T=self.conexion_params['6_T'])
                if getattr(self, 'topology', 'Parallel') == 'Series':
                    self.ptc_field.set_attr(A='var')
            else:
                self.ptc_field.set_attr(
                    E=current_irr, A=self.component_params['ptc_A'],
                    eta_opt=self.component_params['eta_opt'],
                    aoi=self.component_params.get('ptc_aoi', 0),
                    doc=self.component_params.get('ptc_doc', 1),
                    Tamb=self.component_params.get('ptc_tamb', 20),
                    c_1=self.component_params.get('ptc_c_1', 0),
                    c_2=self.component_params.get('ptc_c_2', 0),
                    iam_1=self.component_params.get('ptc_iam_1', 0),
                    iam_2=self.component_params.get('ptc_iam_2', 0))
                # CHX ttd_l placeholder for DOF check; design file overrides with kA
                if hasattr(self, 'charge_tes_hx') and getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.charge_tes_hx.set_attr(ttd_l=20)
                if getattr(self, 'topology', 'Parallel') == 'Series':
                    self.process_hx.set_attr(Q=None)
                    if hasattr(self, 'ptc_field_A_designed'):
                        self.ptc_field.set_attr(A=self.ptc_field_A_designed)
                else:
                    pass
        
        elif TESmode == '2':
            # All flow from PTC to process
            self.create_network(mode=2, design_mode=mode)
            self.preheater_hx.set_attr(Q=0)
            if mode == 'design':
                self.ptc_field.set_attr(
                    aoi=self.component_params['ptc_aoi'], doc=self.component_params['ptc_doc'],
                    Tamb=self.component_params['ptc_tamb'], A='var',
                    eta_opt=self.component_params['eta_opt'], c_1=self.component_params['ptc_c_1'],
                    c_2=self.component_params['ptc_c_2'], E=self.component_params['ptc_E'],
                    iam_1=self.component_params['ptc_iam_1'], iam_2=self.component_params['ptc_iam_2'])
            else:
                self.ptc_field.set_attr(
                    E=current_irr, A='var',
                    eta_opt=self.component_params['eta_opt'],
                    aoi=self.component_params.get('ptc_aoi', 0),
                    doc=self.component_params.get('ptc_doc', 1),
                    Tamb=self.component_params.get('ptc_tamb', 20),
                    c_1=self.component_params.get('ptc_c_1', 0),
                    c_2=self.component_params.get('ptc_c_2', 0),
                    iam_1=self.component_params.get('ptc_iam_1', 0),
                    iam_2=self.component_params.get('ptc_iam_2', 0))
                A_guess = abs(self.component_params.get('PR_Q', 450000)) / (max(current_irr, 100) * self.component_params.get('eta_opt', 0.75))
                try: self.ptc_field.A.val = A_guess
                except: pass
                # Set initial guess for A to avoid solver stall
                A_guess = 1e6 / (max(current_irr, 100) * self.component_params['eta_opt'])
                self.ptc_field.A.val = A_guess
        elif TESmode == '3':
            from tespy.connections import Ref
            self.create_network(mode=3, design_mode=mode)
            self.tes.set_state('discharge')
            
            self.conn_04.set_attr(T=Ref(self.conn_15, 1, 20))   # T04 = T15 - 20
            self.conn_11.set_attr(T=None)
            self.conn_16.set_attr(T=None)
            
            # DHX ttd_l placeholder for DOF check; design file overrides with kA
            if hasattr(self, 'discharge_tes_hx') and getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.discharge_tes_hx.set_attr(ttd_l=20)
            
            # Regime selection (offdesign only)
            if mode != 'design':
                t_ph_out = self.conexion_params['5_T']
                TES_top = profile[-1] if prev_TES_lay == 'Discharge' else profile[0]
                if TES_top >= t_ph_out:
                    self.conn_05.set_attr(T=None)
                    self.preheater_hx.set_attr(Q=0)
            
            # DHX ttd_l placeholder for DOF check; design file overrides with kA
            if hasattr(self, 'discharge_tes_hx') and getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.discharge_tes_hx.set_attr(ttd_l=20)
            
            # Regime selection (offdesign only)
            if mode != 'design':
                t_ph_out = self.conexion_params['5_T']
                TES_top = profile[-1] if prev_TES_lay == 'Discharge' else profile[0]
                if TES_top >= t_ph_out:
                    self.conn_05.set_attr(T=None)

        elif TESmode == '4':
            self.create_network(mode=4, design_mode=mode)
             
        elif TESmode == '5':
            # Mode 5: Series high-T charge (PTC -> HX -> PH -> PR -> CC)
            # Uses its own high-temperature charge HX (sized via ttd_l)
            self.create_network(mode=5, design_mode=mode)
            self.tes.set_state('charge')
            
            TES_bot = self.tes.profile[-1]
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                T14_val = min(TES_bot + 60, 580)
                self.conn_14.set_attr(T=T14_val)
            self.conn_10.set_attr(T=TES_bot if getattr(self, 'tank_config', 'indirect') == 'direct' else None)
            self.preheater_hx.set_attr(pr=1.0)
            
            if mode == 'offdesign':
                self.ptc_field.set_attr(
                    E=current_irr, A=self.component_params['ptc_A'],
                    eta_opt=self.component_params['eta_opt'],
                    aoi=self.component_params.get('ptc_aoi', 0),
                    doc=self.component_params.get('ptc_doc', 1),
                    Tamb=self.component_params.get('ptc_tamb', 20),
                    c_1=self.component_params.get('ptc_c_1', 0),
                    c_2=self.component_params.get('ptc_c_2', 0),
                    iam_1=self.component_params.get('ptc_iam_1', 0),
                    iam_2=self.component_params.get('ptc_iam_2', 0))
                # CHX ttd_l placeholder for DOF check; design file overrides with kA
                if hasattr(self, 'charge_tes_hx') and getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.charge_tes_hx.set_attr(ttd_l=20)

        elif TESmode == '6':
            is_m6par = (getattr(self, 'topology', 'Parallel') == 'Parallel')
            self.create_network(mode=6, design_mode=mode)
            self.tes.set_state('charge')
            
            TES_bot = self.tes.profile[-1]
            
            if is_m6par:
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_14.set_attr(T=TES_bot + 40)
                self.conn_02.set_attr(T=self.conexion_params['5_T'])
                if mode == 'design':
                    self.ptc_field.set_attr(
                        A=self.component_params['ptc_A'], E=self.component_params['ptc_E'],
                        eta_opt=self.component_params['eta_opt'],
                        aoi=self.component_params.get('ptc_aoi', 0),
                        doc=self.component_params.get('ptc_doc', 1),
                        Tamb=self.component_params.get('ptc_tamb', 20),
                        c_1=self.component_params.get('ptc_c_1', 0),
                        c_2=self.component_params.get('ptc_c_2', 0),
                        iam_1=self.component_params.get('ptc_iam_1', 0),
                        iam_2=self.component_params.get('ptc_iam_2', 0)
                    )
                else:
                    self.ptc_field.set_attr(
                        E=current_irr, A=self.component_params['ptc_A'],
                        eta_opt=self.component_params['eta_opt'],
                        aoi=self.component_params.get('ptc_aoi', 0),
                        doc=self.component_params.get('ptc_doc', 1),
                        Tamb=self.component_params.get('ptc_tamb', 20),
                        c_1=self.component_params.get('ptc_c_1', 0),
                        c_2=self.component_params.get('ptc_c_2', 0),
                        iam_1=self.component_params.get('ptc_iam_1', 0),
                        iam_2=self.component_params.get('ptc_iam_2', 0)
                    )
                self.process_hx.set_attr(Q=self.component_params['PR_Q'])
                self.conn_05.set_attr(T=self.conexion_params['5_T'])
                self.conn_06.set_attr(T=self.conexion_params['6_T'])
                if hasattr(self, 'charge_hx_kA') and self.charge_hx_kA:
                    self.charge_tes_hx.set_attr(kA=self.charge_hx_kA)
            else:
                if hasattr(self, 'charge_hx_kA') and self.charge_hx_kA:
                    self.charge_tes_hx.set_attr(kA=self.charge_hx_kA)
                if mode == 'design':
                    self.ptc_field.set_attr(A='var')
                else:
                    self.ptc_field.set_attr(E=current_irr)
                    self.process_hx.set_attr(Q=None)
                    if hasattr(self, 'ptc_field_A_designed'):
                        self.ptc_field.set_attr(A=self.ptc_field_A_designed)

        else:   
            raise ValueError(f"Unknown mode {TESmode}")
 
 
    def solve_network(self, mode='design', design_path="base_design", TESmode='1', use_init_path=False):
        """
        Attempts to solve the network in the specified mode (default: 'design').
        Raises an exception if the solver fails.
        
        Args:
            mode (str): 'design' or 'offdesign' (TESPy modes).
            use_init_path (bool): if True, warm-start offdesign from design solution.
        """

        import os, shutil, time
        base_dir = '.tespy_cache'
        os.makedirs(base_dir, exist_ok=True)
        name = os.path.join(base_dir, f'base_design_{TESmode}')        
        if mode == 'design':

            self.network.solve(mode=mode, max_iter=100)
            abs_name = os.path.abspath(name)
            if os.path.exists(abs_name):
                try:
                    if os.path.isfile(abs_name):
                        os.remove(abs_name)
                    else:
                        import uuid
                        new_name = abs_name + "_old_" + uuid.uuid4().hex[:6]
                        os.rename(abs_name, new_name)
                except Exception as e:
                    print(f"Could not rename {abs_name}: {e}")
            self.network.save(name)
            # Persist designed values for cross-mode use
            if (hasattr(self, 'ptc_field') and self.ptc_field is not None
                    and self.ptc_field.A.val is not None):
                self.ptc_field_A_designed = self.ptc_field.A.val
            if (TESmode == '1' and hasattr(self, 'charge_tes_hx')
                    and self.charge_tes_hx.kA.val is not None):
                # Store kA in-memory for cross-mode use (Modes 5, 6 share the same HX)
                self.charge_hx_kA = self.charge_tes_hx.kA.val
        else:
            design_path_full = os.path.join(base_dir, f'base_design_{TESmode}')
            kwargs = {'mode': mode, 'max_iter': 200, 'design_path': design_path_full}
            if use_init_path:
                kwargs['init_path'] = design_path_full
            self.network.solve(**kwargs)
            #if not self.network.converged:
            #    raise RuntimeError("TESPy solver did not converge.")

