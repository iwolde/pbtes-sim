"""Fix remaining indentation errors by surgically replacing broken sections."""
with open('coreV5_indirect_parallel.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix pattern: "tank_cfg = getattr(...)" followed by indented code that had its parent if removed
# These sit inside mode-specific routing sections

# Fix Mode 1 routing (around line 748 area)
old = """        if mode == 1:
            tank_cfg = getattr(self, 'tank_config', 'indirect')
                self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.splitter1, 'in1', label='02_PTC_SP1')
                self.conn_04 = tpcn.Connection(self.splitter1, 'out1', self.preheater_hx, 'in1', label='04_SP1_PH')
                self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
                self.network.add_conns(self.conn_01, self.conn_02, self.conn_04, self.conn_05, self.conn_06, self.conn_09)
                for conn in [self.conn_01, self.conn_02, self.conn_04, self.conn_05, self.conn_06, self.conn_09]:
                    conn.set_attr(T0=500, h0=700, m0=30, p0=5)"""

if old in content:
    print('Found Mode 1 broken block, replacing...')
else:
    print('Mode 1 broken block NOT found, checking variations...')
    # Try without the trailing comment
    for snippet in old.split('\n'):
        if snippet.strip() and snippet.strip() not in content:
            print(f'  Missing: {snippet.strip()[:60]}')
