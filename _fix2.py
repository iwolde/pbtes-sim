"""Replace corrupted mode routing (lines 795-835) with correct code."""
with open('coreV5_indirect_parallel.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find start of corrupted section (elif mode == 3:)
start = None
for i, line in enumerate(lines):
    if 'elif mode == 3:' in line and i > 700:
        start = i
        break

# Find end of corrupted section (common block start)
end = None
for i in range(start, len(lines)):
    if '=== STRUCTURAL parameters' in lines[i]:
        end = i
        break

print(f'Replacing lines {start+1}-{end}')

correct = """        elif mode == 3:
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
                self.conn_15.set_attr(p=self.conexion_params['15_p'], fluid=self.conexion_params['15_f'])
                self.discharge_tes_hx.set_attr(pr1=1.0, pr2=1.0)
            else:
                self.conn_04 = tpcn.Connection(self.discharge_tes_hx, 'out1', self.preheater_hx, 'in1', label='04_DHX_PH')
                self.conn_11 = tpcn.Connection(self.cycle_closer, 'out1', self.discharge_tes_hx, 'in1', label='11_CC_DHX')
                self.network.add_conns(self.conn_04, self.conn_05, self.conn_06, self.conn_11)
                for conn in [self.conn_04, self.conn_05, self.conn_06, self.conn_11]:
                    conn.set_attr(T0=500, h0=714, m0=35, p0=5)
                self.discharge_tes_hx.set_attr(pr=0.98)

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

"""

correct_lines = correct.split('\n')

# Replace
new_lines = lines[:start] + [l + '\n' for l in correct_lines] + lines[end:]
with open('coreV5_indirect_parallel.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print(f'Done. New file has {len(new_lines)} lines.')
