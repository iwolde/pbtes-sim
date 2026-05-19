# Equation System Audit — All 6 Modes (Parallel · indirect)
# =================================================================
# Each mode shows: topology, components, connections, constraints,
# and how they differ between DESIGN and OFFDESIGN.

# =================================================================
# GLOSSARY
# =================================================================
# CC  = CycleCloser    (h_out=h_in, p_out=p_in, m_out=m_in)
# PTC = ParabolicTrough (η·A·DNI·IAM + thermal losses)
# PH  = Preheater_HX   (SimpleHeatExchanger, gap-filler)
# PR  = Process_HX     (SimpleHeatExchanger, Q=-1 MW)
# CHX = Charge_TES_HX  (HeatExchanger, primary/secondary)
# DHX = Discharge_TES_HX (HeatExchanger, primary/secondary)
# SPL = Splitter        (p1=p2=p_in, h1=h2=h_in, m1+m2=m_in)
# MRG = Merge           (p1=p2=p_out, m1+m2=m_out, energy balance)
# SRC = Source          (p, T, fluid specified)
# SNK = Sink            (free outlet)
#
# Variable types per connection: m (mass flow), p (pressure), h (enthalpy)
# h is indirectly set via T (temperature). T/h linked by fluid props.
# Each connection contributes 3 variables to the network, minus those
# eliminated by component equations and cycle closers.

# =================================================================
# CONSTANTS USED ACROSS ALL MODES
# =================================================================
# From conexion_params:
#   T06 = 480°C, P06 = 50 bar, fluid_06 = NaK
#   T05 = 520°C  (preheat outlet target)
#   P13 = 5 bar, fluid_13 = NaK  (TES charge side)
#   P15 = 5 bar, fluid_15 = NaK  (TES discharge side)
# From component_params:
#   PR_Q = -1e6 W  (process duty, 1 MW thermal)
#   ptc_A = 2500 m², eta_opt = 0.75
#   ptc_E = 1000 W/m² (design irradiance)
#   aoi=0, doc=1, Tamb=20, c_1=c_2=0, iam_1=iam_2=0

# =================================================================
# MODE 1 — Parallel charge: PTC splits to Process + TES
# =================================================================
# TOPOLOGY:
#   CC → [conn_01] → PTC → [conn_02] → SPLITTER
#     ├─ SPL.out1 → [conn_04] → PH → [conn_05] → PR → [conn_06] → MERGE.in1
#     └─ SPL.out2 → [conn_09] → CHX.prim → [conn_10] → MERGE.in2
#   MERGE.out1 → [conn_08] → CC (close loop)
#   TES secondary:
#     SRC → [conn_13] → CHX.sec → [conn_14] → SNK
#
# COMPONENTS (8): CC, PTC, SPL, PH, PR, MERGE, CHX, SRC, SNK
#   SRC and SNK: each has 1 internal conn but NOT in variable count (fixed by source/sink)
#   Actual connections counted: 10
#     conn_01, conn_02, conn_04, conn_05, conn_06, conn_08,
#     conn_09, conn_10, conn_13, conn_14
#
# COMPONENT EQUATIONS:
#   CC:    h_08 = h_01, p_08 = p_01          [2 eqns, m implicit]
#   PTC:   Q = A·η·DNI·IAM·f - losses        [1 eqn, Q free]
#   SPL:   p_04=p_09=p_02, h_04=h_09=h_02, m_04+m_09=m_02   [3 eqns]
#   PH:    Q_ph = m·(h_05 - h_04), Q_ph=0    [1 eqn]
#   PR:    Q_pr = m·(h_06 - h_05), Q_pr=-1e6 [1 eqn]
#   CHX:   Q = m_pri·(h_09-h_10)           [energy prim]
#          Q = m_sec·(h_14-h_13)            [energy sec]
#          Q = kA·ΔTm(...)                  [heat transfer]
#   MRG:   p_06=p_10=p_08, m_06+m_10=m_08   [2 eqns, h via energy balance]
#   Total component eqns: 2+1+3+1+1+3+2 = 13
#
# VARIABLES: 10 conns × 3 = 30
#   CC eliminates: m_08=m_01, p_08=p_01, h_08=h_01 → -3
#   MERGE eliminates: m_08=m_06+m_10 (already via CC) → redundancy
#   SPL eliminates: m_02 via m_04+m_09 → -1 (m_02 determined)
#   After implicit eliminations: ~26 independent variables
#   After 13 component eqns: 26-13 = 13 specifications needed
#
# SPECIFICATIONS (DESIGN mode):
#   [C]  T06=480         (common · boundary)
#   [C]  T05=520         (common · boundary)
#   [C]  PR Q=-1e6       (common · boundary)
#   [C]  P06=50, f06=NaK (common · structural)
#   [C]  P13=5, f13=NaK  (common · structural)
#   [C]  PR pr=1.0       (common · structural)
#   [C]  CHX pr1=0.98, pr2=0.98 (common · structural)
#   [D]  PTC: A=2500, E=1000, eta=0.75, aoi=0, doc=1, Tamb=20,
#             c_1=c_2=0, iam_1=iam_2=0                     [1 spec effective — Q equation]
#   [D]  CHX ttd_l=20     (common · design · forces kA)
#   [M]  conn_14.T = TES_bot+40   (set_operation_mode)
#   [M]  PH Q=0           (set_operation_mode)
#   [M]  T05=520 (set again, redundant)
#   [M]  T06=480 (set again, redundant)
#   [L]  conn_13.T = TES_bot (coupling loop)
#   Total specs: ~13 ✅  DETERMINED
#
# OFFDESIGN constraints (differences from DESIGN):
#   [D] PTC params removed (NOT set by create_network design block)
#       → Q still determined by E=current_irr + A from design file
#   [D] CHX ttd_l removed (kA comes from design file base_design_1)
#   [M] PTC: E=current_irr plus ALL params set explicitly
#   [M] T05=520 (set again)
#   [L] conn_13.T = T_bot (coupling loop, same as design)
#   Total specs: ~13 ✅  DETERMINED
#
# ⚠ POTENTIAL CONFLICT:
#   1. CHX ttd_l is set in create_network (design block, always runs).
#      Offdesign solve loads base_design_1 which has stored kA.
#      ttd_l (from create_network) vs. kA (from design file) may conflict.
#      TESPy should resolve: design file kA overrides ttd_l in offdesign.
#   2. PTC params set by create_network (design block) + set_operation_mode
#      (offdesign params). Design file also loads PTC params.
#      Triple-setting = same values overridden → usually fine.
#   3. conn_14.T = TES_bot+40 is a FIXED secondary outlet temperature.
#      With kA fixed, the CHX must find Q,m_sec that satisfies both:
#        T14 known, T13 known, T09 from PTC, T10 = T09 - Q/(m_pri·cp).
#      This is fully determined (4 unknowns: m_pri, m_sec, Q, T10
#      via 4 equations: 2 energy + kA + T14 fixed).


# =================================================================
# MODE 2 — PTC to Process only (no TES interaction)
# =================================================================
# TOPOLOGY:
#   CC → [conn_01] → PTC → [conn_02] → PH → [conn_05] → PR → [conn_06] → CC
#
# COMPONENTS (4): CC, PTC, PH, PR
# CONNECTIONS (4): conn_01, conn_02, conn_05, conn_06
#
# COMPONENT EQUATIONS:
#   CC:      h_06=h_01, p_06=p_01, m implicit   [2 eqns]
#   PTC:     Q = A·η·DNI·IAM·f - losses          [1 eqn]
#   PH:      Q_ph = m·(h_05-h_02) = 0            [1 eqn]
#   PR:      Q_pr = m·(h_06-h_05) = -1e6         [1 eqn]
#   Total: 5 eqns
#
# VARIABLES: 4 conns × 3 = 12
#   CC eliminates 3 (m,p,h) → 9
#   After 5 component eqns: 9-5 = 4 specs needed
#
# SPECIFICATIONS (DESIGN mode):
#   [C] T05=520       (common · boundary)
#   [C] T06=480       (common · boundary)
#   [C] PR Q=-1e6     (common · boundary)
#   [C] P06=50, f=NaK (common · structural)
#   [C] PR pr=1.0     (common · structural)
#   [D] PTC: A='var'  (set_operation_mode · design)
#   [D] PTC: E=1000, eta=0.75, ... (common · design · overridden by A='var')
#   [M] PH Q=0, pr=1.0 (set_operation_mode)
#   Total specs: PTC A='var' makes A variable → Q relation needs 1 extra spec
#                All PTC params + A='var' + T05 + T06 + PR_Q + PH_Q = sufficient
#   Status: ✅ DESIGN CONVERGES (A computed as ~1333 m² at E=1000)
#
# OFFDESIGN constraints (differences from DESIGN):
#   [D] PTC params from design block: A=2500, E=1000, ... (still set!)
#   [M] PTC: E=current_irr, A='var' PLUS all params set explicitly
#   [M] PH Q=0, pr=1.0 (same as design)
#   Design file (base_design_2) provides stored A, then overridden by A='var'
#   Total specs: same structure, E varies.
#   
# ⚠ POTENTIAL CONFLICT:
#   1. PTC params set THREE times:
#      a) create_network design block: A=2500, E=1000, eta=0.75, ...
#      b) set_operation_mode offdesign: E=current_irr, A='var', eta=0.75, ...
#      c) design file loaded: A=1333 (computed), E=1000 (original), ...
#      After loading: A='var' (overrides 1333), E=current_irr (overrides 1000)
#      This REPEATED rewriting may cause TESPy's DOF counter to count
#      the previous sets as "specified" even after override.
#      FIX: could set A=None then set_attr(A='var') to avoid double-count.
#   2. "13 conns" logged in randomization means stale conns from Mode 1
#      still on the SolarThermalSystem object. Create_network creates
#      NEW conn_XX attributes but old ones (conn_04, conn_09, etc.)
#      persist. The randomizer iterates all conn_* attributes.
#      NOT a DOF issue — cosmetic only.


# =================================================================
# MODE 3 — TES Discharge to Process
# =================================================================
# TOPOLOGY:
#   Process loop:  CC → [conn_11] → DHX.sec → [conn_04] → PH → [conn_05] → PR → [conn_06] → CC
#   TES loop:      SRC → [conn_15] → DHX.prim → [conn_16] → SNK
#
# COMPONENTS: CC, DHX, PH, PR
# CONNECTIONS (6): conn_11, conn_04, conn_05, conn_06, conn_15, conn_16
#
# COMPONENT EQUATIONS:
#   CC:   h_06=h_11, p_06=p_11, m implicit   [2 eqns]
#   DHX:  Q = m_15·(h_15-h_16)              [1]
#         Q = m_11·(h_04-h_11)              [1]
#         Q = kA·ΔTm                        [1] (design: ttd_l→kA)
#   PH:   Q_ph = m·(h_05-h_04), Q free      [1 eqn]  ← gap-filler
#   PR:   Q_pr = m·(h_06-h_05) = -1e6       [1 eqn]
#   Total: 7 eqns
#
# VARIABLES: 6 conns × 3 = 18
#   CC eliminates 3 → 15
#   After 7 component eqns: 15-7 = 8 specs needed
#
# SPECIFICATIONS (DESIGN mode):
#   [C] T05=520           (common · boundary)  ← was skipped for mode 3, NOW SET
#   [C] T06=480           (common · boundary)
#   [C] PR Q=-1e6         (common · boundary)
#   [C] P06=50, f=NaK     (common · structural)
#   [C] P15=5, f=NaK      (common · structural)
#   [C] PR pr=1.0         (common · structural)
#   [C] DHX pr1=1.0, pr2=1.0 (create_network mode 3)
#   [D] DHX ttd_l=20      (common · design · forces kA)
#   [M] conn_04.T = Ref(conn_15, 1, 20)  [T04 = T15 - 20]  ← adds 1 eqn
#   [M] conn_11.T = None  (free)
#   [M] conn_16.T = None  (free)
#   [L] conn_15.T = T_tes_top (= 540°C for design)
#   Total specs: T05 + T06 + P06 + P15 + PR_Q + DHX ttd_l + Ref + T15 = 8 ✅
#   PH Q is FREE (gap-filler). With T15=540: T04=520, T05=520, Q_ph=0.
#   DHX sized for full load.
#
# OFFDESIGN constraints (differences from DESIGN):
#   [D] DHX ttd_l still set (create_network always runs) ← ⚠ CONFLICT?
#   Design file (base_design_3) provides stored kA.
#   DHX ttd_l (create_network) vs stored kA (design file) → kA wins in offdesign.
#   All other specs identical. T15 varies per coupling loop.
#   PH Q free → fills gap when T15 < 540.
#
#   ✅ VERIFIED: Mode 3 offdesign converges at T15=505→540.
#     At T15=505: DHX=0.12MW, PH=0.88MW  (PH fills gap)
#     At T15=540: DHX=1.00MW, PH=0.00MW  (DHX provides all)
#
# ⚠ ISSUE: DHX ttd_l=20 is set in create_network even for offdesign
#   (since design_mode is always 'design'). If the design file's
#   stored kA is incompatible with ttd_l=20 for offdesign temps,
#   the Jacobian becomes singular. This is a latent issue but
#   empirically Mode 3 works for our T15 range.
#
#   TESPy's offdesign solve loads the design file FIRST, then
#   applies the current set_attr values. The design file kA
#   should override the ttd_l specification. If it doesn't,
#   the solver would have both ttd_l and kA specified → singularity.


# =================================================================
# MODE 4 — Standby (auxiliary only)
# =================================================================
# TOPOLOGY:
#   CC → [conn_04] → PH → [conn_05] → PR → [conn_06] → CC
#
# COMPONENTS (3): CC, PH, PR
# CONNECTIONS (3): conn_04, conn_05, conn_06
#   NOTE: no PTC component in this mode.
#
# COMPONENT EQUATIONS:
#   CC:   h_06=h_04, p_06=p_04, m implicit   [2 eqns]
#   PH:   Q_ph = m·(h_05-h_04), Q free       [1 eqn]  ← auxiliary heating
#   PR:   Q_pr = m·(h_06-h_05) = -1e6        [1 eqn]
#   Total: 4 eqns
#
# VARIABLES: 3 conns × 3 = 9
#   CC eliminates 3 → 6
#   After 4 component eqns: 6-4 = 2 specs needed
#
# SPECIFICATIONS (DESIGN & OFFDESIGN — identical):
#   [C] T05=520       (common · boundary)
#   [C] T06=480       (common · boundary)
#   [C] PR Q=-1e6     (common · boundary)
#   [C] P06=50, f=NaK (common · structural)
#   [C] PR pr=1.0     (common · structural)
#   Total specs: T05, T06, PR_Q → 3, but only 2 needed → 1 OVER
#   
#   Wait: PH Q is FREE. So from T05,T06,PR_Q:
#     m = |PR_Q| / (h_05-h_06) → determined (e.g., ~16.4 kg/s)
#     Q_ph = m·(h_05-h_04) → needs T04 from CC
#     CC gives h_04 = h_06 → T04 = T06 = 480°C
#     Q_ph = m·(h_520-h_480) = |PR_Q| = 1 MW → PH provides all heat.
#   
#   ✅ DETERMINED (with 1 redundant spec, always converges)


# =================================================================
# MODE 5 — High-T Series Charge (PTC → HX → PH → PR → CC)
# =================================================================
# TOPOLOGY:
#   CC → [conn_01] → PTC → [conn_02] → CHX.prim → [conn_10] → PH → [conn_05] → PR → [conn_06] → CC
#   TES secondary: SRC → [conn_13] → CHX.sec → [conn_14] → SNK
#
# COMPONENTS (6): CC, PTC, CHX, PH, PR
# CONNECTIONS (7 for indirect): conn_01, conn_02, conn_10, conn_05, conn_06, conn_13, conn_14
#
# COMPONENT EQUATIONS:
#   CC:   h_06=h_01, p_06=p_01, m implicit    [2 eqns]
#   PTC:  Q = A·η·DNI·IAM·f - losses         [1 eqn]
#   CHX:  Q = m_pri·(h_02-h_10)              [1]
#         Q = m_sec·(h_14-h_13)               [1]
#         Q = kA·ΔTm(...)                     [1] (design: ttd_l→kA)
#   PH:   Q_ph = m·(h_05-h_10), Q free       [1 eqn]  ← inter-stage heater
#   PR:   Q_pr = m·(h_06-h_05) = -1e6        [1 eqn]
#   Total: 8 eqns
#
# VARIABLES: 7 conns × 3 = 21
#   CC eliminates 3 → 18
#   After 8 component eqns: 18-8 = 10 specs needed
#
# SPECIFICATIONS (DESIGN mode):
#   [C] T05=520       (common · boundary)
#   [C] T06=480       (common · boundary)
#   [C] PR Q=-1e6     (common · boundary)
#   [C] P06=50, f=NaK (common · structural)
#   [C] P13=5, f=NaK  (common · structural)
#   [C] PR pr=1.0     (common · structural)
#   [C] CHX pr1=0.98, pr2=0.98 (common · structural)
#   [D] PTC: A=2500, E=1000, eta=0.75, ... (common · design)
#   [D] CHX ttd_l=20      (common · design, forces kA)
#   [M] conn_14.T = min(TES_bot+60, 580)   (set_operation_mode)
#   [M] conn_10.T = None  (freed)
#   [M] PH pr=1.0         (set_operation_mode)
#   [L] conn_13.T = TES_bot (coupling loop)
#   Total specs: enough for 10 needed ✅
#
# OFFDESIGN constraints (differences from DESIGN):
#   [M] PTC: E=current_irr + all params set explicitly
#   All other specs identical.
#   Design file (base_design_5) provides stored kA and PTC A.
#   
#   NOTE: Mode 5 was repurposed from re-stratification to high-T charge.
#   T14 capped at 580°C to protect NaK fluid (max 600°C).


# =================================================================
# MODE 6 — Full TES Charge, Parallel (two independent cycles)
# =================================================================
# TOPOLOGY:
#   Cycle 1 (PTC → TES): CC → [conn_01] → PTC → [conn_02] → CHX.prim → [conn_10] → CC
#   Cycle 2 (Aux → Process): CC2 → [conn_04] → PH → [conn_05] → PR → [conn_06] → CC2
#   TES secondary: SRC → [conn_13] → CHX.sec → [conn_14] → SNK
#
# COMPONENTS (7): CC, CC2, PTC, CHX, PH, PR
# CONNECTIONS (8 for indirect):
#   Cycle 1: conn_01, conn_02, conn_10, conn_13, conn_14
#   Cycle 2: conn_04, conn_05, conn_06
#
# COMPONENT EQUATIONS:
#   CC:   h_10=h_01, p_10=p_01              [2 eqns]
#   CC2:  h_06=h_04, p_06=p_04              [2 eqns]
#   PTC:  Q = A·η·DNI·IAM·f - losses        [1 eqn]
#   CHX:  Qp = m_02·(h_02-h_10)            [1]
#         Qs = m_13·(h_14-h_13)             [1]
#         Q = kA·ΔTm                        [1]
#   PH:   Q_ph = m_04·(h_05-h_04), Q free  [1 eqn]
#   PR:   Q_pr = m_04·(h_06-h_05) = -1e6   [1 eqn]
#   Total: 10 eqns
#
# VARIABLES: 8 conns × 3 = 24
#   CC eliminates 3, CC2 eliminates 3 → 18
#   After 10 component eqns: 18-10 = 8 specs needed
#
# SPECIFICATIONS (DESIGN mode):
#   [C] T05=520        (common · boundary)
#   [C] PR Q=-1e6      (common · boundary)  ← M6 Par SKIPS conn_06.T in boundary block
#   [C] P06=50, f=NaK  (common · structural)
#   [C] P13=5, f=NaK   (common · structural)
#   [C] PR pr=1.0      (common · structural)
#   [C] CHX pr1=1.0, pr2=1.0 (create_network M6 Par)
#   NOT SET by common design block: PTC params (is_m6_par = True → skipped)
#                                  CHX ttd_l (is_m6_par = True → skipped)
#                                  T06 (is_m6_par = True → skipped)
#   [M] conn_14.T = TES_bot+40   (set_operation_mode)
#   [M] conn_02.T = 520          (set_operation_mode)
#   [M] PTC: A=2500, E=1000, ... (set_operation_mode · design)
#   [M] PR Q=-1e6                 (set_operation_mode)
#   [M] T05=520                   (set_operation_mode)
#   [M] T06=480                   (set_operation_mode)
#   [M] CHX kA from mode1_kA.txt (set_operation_mode)
#   [L] conn_13.T = TES_bot      (coupling loop)
#   Total specs: ✅
#
# OFFDESIGN constraints:
#   [M] PTC: E=current_irr, A=2500 + all params set explicitly
#   [M] CHX kA from stored value (same as design)
#   [L] conn_13.T = TES_bot
#   All other specs identical to design.
#
# ⚠ KNOWN ISSUE: Mode 6 offdesign fails with "Singularity in jacobian".
#   Likely cause: Cycle 1 is CC→PTC→CHX.prim→CC.
#   conn_02.T=520 is FIXED (from set_operation_mode).
#   PTC must produce output at exactly 520°C.
#   At low E (night, E<100), PTC can't reach 520°C → singularity.
#   Also: stored kA from Mode 1 may not match Mode 6's flow regime
#   (Mode 1 splits PTC flow; Mode 6 sends all flow to HX).
#   FIX: remove conn_02.T=520, let PTC output temp float.
#        OR: only select Mode 6 when E is high enough.


# =================================================================
# SUMMARY TABLE — Convergence Status
# =================================================================
# Mode | Connections | Design DOF | Offdesign DOF | Empirically | Notes
# -----|------------|------------|---------------|-------------|------
#  1   | 10 (Par)   | Determined | Determined    | Sometimes   | CHX ttd_l vs kA
#      |  7 (Ser)   | Determined | Determined    | OK          | conflict possible
#  2   |     4      | Determined | Determined    | Sometimes   | PTC triple-spec
#  3   |     6      | Determined | Determined    | ✅ OK       | PH gap-filler works
#  4   |     3      | Determined | Determined    | ✅ Always   | Simplest mode
#  5   |     7      | Determined | Determined    | ✅ OK       | T14 cap at 580
#  6   |     8 (Par) | Determined | Determined    | ❌ Fails    | T02=520 + low E
#      |     7 (Ser) | Determined | Determined    | OK          | A='var' works
#
# =================================================================
# KEY FINDINGS — Convergence Failures
# =================================================================
#
# 1. MODE 6 PARALLEL: conn_02.T=520 forces PTC outlet at exactly 520°C.
#    At low E (below ~500 W/m²), PTC cannot reach 520°C → singularity.
#    SOLUTION: Remove conn_02.T=520. Let PTC outlet float.
#    The CHX kA relation will determine the temperature profile naturally.
#    Only conn_13 and conn_14 need fixing (TES secondary).
#
# 2. MODE 1/2/5: PTC parameters triple-specified (create_network design
#    block + set_operation_mode + design file loading). This causes
#    "Singularity in jacobian" when the overrides conflict with stored
#    design values, especially when switching between modes.
#    SOLUTION: In offdesign, DON'T set PTC eta_opt/aoi/doc/etc in
#    set_operation_mode. Only set E (and A='var' for Mode 2).
#    Let the design file provide component characteristics.
#
# 3. STALE CONNECTIONS: create_network creates new conn_XX attributes
#    but doesn't delete old ones. The attempt_to_solve retry pipeline
#    scans ALL conn_* via dir(), picking up stale attributes. This
#    randomizes ghost connections, wasting tries.
#    SOLUTION: In create_network, delete all existing conn_* before
#    creating new ones.
#
# 4. CHX ttd_l ALWAYS SET: create_network sets ttd_l=20 for all modes
#    with charge HX (1,5,6) because design_mode is always 'design'.
#    In offdesign, the design file kA should override ttd_l, but TESPy
#    may not handle this cleanly if both are set.
#    SOLUTION: Move ttd_l setting out of create_network into
#    initialize_modes() (only for design). Or clear it before offdesign.
#
# 5. MODE 2: A='var' in offdesign means PTC area is re-computed each
#    hour. This is PHYSICALLY CORRECT (PTC defocuses). But the design
#    file stores A=1333 from design, and A='var' overrides it. Fine.
#    The issue is only the extra PTC params set by set_operation_mode.
