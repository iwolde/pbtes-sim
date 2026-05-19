"""
Assessment 06 — Publication-Quality Figures
Generates all article figures from baseline and parametric results.
Outputs SVG + PDF to article_results/06_figures/
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from scipy.interpolate import griddata

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'article_results')
FIG_DIR = os.path.join(BASE_DIR, '06_figures')
os.makedirs(FIG_DIR, exist_ok=True)

# ─── Journal-quality matplotlib defaults ──────────────────────────────
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 11,
    'axes.labelsize': 13,
    'axes.titlesize': 13,
    'xtick.labelsize': 11,
    'ytick.labelsize': 11,
    'legend.fontsize': 10,
    'figure.dpi': 300,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linestyle': '--',
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.05,
})


def _save(fig, name):
    """Save a figure as both SVG and PDF."""
    fig.savefig(os.path.join(FIG_DIR, f'{name}.svg'), format='svg')
    fig.savefig(os.path.join(FIG_DIR, f'{name}.pdf'), format='pdf')
    plt.close(fig)
    print(f'  ✔ {name}.svg / .pdf')


# ─── Figure 1: Parametric contour — Solar Fraction ───────────────────
def fig_parametric_contours():
    csv = os.path.join(BASE_DIR, '02_parametric', 'parametric_sweep.csv')
    if not os.path.exists(csv):
        print('  ⚠ parametric_sweep.csv not found')
        return
    df = pd.read_csv(csv)
    ok = df[df['Status'] == 'ok']
    if len(ok) < 4:
        print('  ⚠ Not enough successful runs for contour')
        return

    D = ok['Tank diameter (m)'].values
    L = ok['Tank length (m)'].values

    # Contour grid
    Di = np.linspace(D.min(), D.max(), 60)
    Li = np.linspace(L.min(), L.max(), 60)
    Dg, Lg = np.meshgrid(Di, Li)

    # ── Solar Fraction contour ──
    SF = ok['Solar Fraction'].values
    SFi = griddata((D, L), SF, (Dg, Lg), method='cubic')

    fig, ax = plt.subplots(figsize=(7, 5.5))
    cs = ax.contourf(Dg, Lg, SFi, levels=15, cmap='plasma')
    ax.scatter(D, L, c='white', edgecolor='k', s=40, zorder=5)
    cb = fig.colorbar(cs, ax=ax, label='Solar Fraction')
    ax.set_xlabel('Tank Diameter (m)')
    ax.set_ylabel('Tank Length (m)')
    ax.set_title('Solar Fraction vs. Tank Geometry')
    _save(fig, 'contour_solar_fraction')

    # ── LCOH contour ──
    LCOH = ok['LCOH ($/kWh)'].values
    LCOHi = griddata((D, L), LCOH, (Dg, Lg), method='cubic')

    fig, ax = plt.subplots(figsize=(7, 5.5))
    cs = ax.contourf(Dg, Lg, LCOHi, levels=15, cmap='viridis_r')
    ax.scatter(D, L, c='white', edgecolor='k', s=40, zorder=5)
    cb = fig.colorbar(cs, ax=ax, label='LCOH (\\$/kWh)')
    ax.set_xlabel('Tank Diameter (m)')
    ax.set_ylabel('Tank Length (m)')
    ax.set_title('LCOH vs. Tank Geometry')
    _save(fig, 'contour_lcoh')


# ─── Figure 2: Baseline time series (modes, energy, TES) ─────────────
def fig_baseline_timeseries():
    csv = os.path.join(BASE_DIR, '01_baseline', 'baseline_parallel.csv')
    if not os.path.exists(csv):
        print('  ⚠ baseline_parallel.csv not found')
        return

    # Load with meta line
    from coreV5 import Reporting
    report = Reporting()
    df, meta = report.load_simulation_from_csv(csv)

    if 'time' not in df.columns:
        print('  ⚠ "time" column missing in baseline CSV')
        return

    df['time'] = pd.to_datetime(df['time'], errors='coerce')

    # ── Mode histogram ──
    if 'TESmode' in df.columns:
        fig, ax = plt.subplots(figsize=(6, 4))
        mode_counts = df['TESmode'].value_counts().sort_index()
        bars = ax.bar(mode_counts.index.astype(str), mode_counts.values, color='steelblue', edgecolor='k')
        ax.set_xlabel('Operating Mode')
        ax.set_ylabel('Hours')
        ax.set_title('Annual Mode Distribution')
        for b in bars:
            ax.annotate(f'{int(b.get_height())}', xy=(b.get_x() + b.get_width()/2, b.get_height()),
                        ha='center', va='bottom', fontsize=9)
        _save(fig, 'mode_histogram')

    # ── Daily cumulative energy ──
    energy_cols = [c for c in ['ptc_total_kJ', 'aux_to_proc_kJ', 'to_tes_kJ', 'tes_to_proc_kJ'] if c in df.columns]
    if energy_cols:
        fig, ax = plt.subplots(figsize=(10, 4.5))
        for col in energy_cols:
            cum = df[col].cumsum() / 3.6e6  # kJ → MWh
            ax.plot(df['time'], cum, label=col.replace('_kJ', '').replace('_', ' ').title())
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Energy (MWh)')
        ax.set_title('Annual Cumulative Energy Balance')
        ax.legend(loc='upper left', framealpha=0.8)
        fig.autofmt_xdate()
        _save(fig, 'cumulative_energy')

    # ── TES top/bottom temperatures (first 30 days) ──
    if 'T_tes_top' in df.columns and 'T_tes_bottom' in df.columns:
        fig, ax = plt.subplots(figsize=(10, 4))
        mask = df['time'] < df['time'].min() + pd.Timedelta(days=30)
        sub = df[mask]
        ax.plot(sub['time'], sub['T_tes_top'], label='TES Top', color='crimson', linewidth=0.8)
        ax.plot(sub['time'], sub['T_tes_bottom'], label='TES Bottom', color='royalblue', linewidth=0.8)
        if 'E' in sub.columns:
            ax2 = ax.twinx()
            ax2.fill_between(sub['time'], 0, sub['E'], alpha=0.15, color='orange', label='DNI')
            ax2.set_ylabel('DNI (W/m²)')
        ax.set_xlabel('Date')
        ax.set_ylabel('Temperature (°C)')
        ax.set_title('TES Temperatures — First 30 Days')
        ax.legend(loc='upper left')
        fig.autofmt_xdate()
        _save(fig, 'tes_temperatures_30d')


# ─── Figure 3: LCOH vs Solar Fraction scatter ────────────────────────
def fig_lcoh_vs_sf():
    csv = os.path.join(BASE_DIR, '02_parametric', 'parametric_sweep.csv')
    if not os.path.exists(csv):
        return
    df = pd.read_csv(csv)
    ok = df[df['Status'] == 'ok']
    if ok.empty:
        return

    fig, ax = plt.subplots(figsize=(7, 5))
    sc = ax.scatter(ok['Solar Fraction'], ok['LCOH ($/kWh)'],
                    c=ok['Tank Volume (m3)'], cmap='coolwarm', s=80, edgecolor='k', alpha=0.85)
    fig.colorbar(sc, ax=ax, label='Tank Volume (m³)')
    ax.set_xlabel('Solar Fraction')
    ax.set_ylabel('LCOH (\\$/kWh)')
    ax.set_title('LCOH vs. Solar Fraction')
    _save(fig, 'lcoh_vs_solar_fraction')


def main():
    print(f'\n{"="*60}')
    print(' Generating publication figures')
    print(f'{"="*60}')

    fig_parametric_contours()
    fig_baseline_timeseries()
    fig_lcoh_vs_sf()

    print(f'\n✅ Assessment 06 complete → {FIG_DIR}')


if __name__ == '__main__':
    main()
