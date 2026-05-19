"""
Assessment 07 — Article Synthesis Generator
Reads all assessment outputs and produces ARTICLE_SYNTHESIS.md
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import json

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'article_results')
SYNTH_DIR = os.path.join(BASE_DIR, '07_synthesis')
os.makedirs(SYNTH_DIR, exist_ok=True)


def main():
    lines = []
    lines.append('# PBTES Digital Twin — Article Synthesis\n')
    lines.append('*Auto-generated from assessment pipeline results.*\n\n')

    # ─── Baseline summary ─────────────────────────────────────────────
    lines.append('## 1. Baseline Annual Simulation\n')
    baseline_csv = os.path.join(BASE_DIR, '01_baseline', 'baseline_parallel.csv')
    if os.path.exists(baseline_csv):
        from coreV5 import Reporting
        report = Reporting()
        df, meta = report.load_simulation_from_csv(baseline_csv)

        metrics = meta.get('extra', {}).get('metrics', {})
        sf = metrics.get('solar_fraction', 'N/A')
        spf = metrics.get('spf', 'N/A')

        n_steps = len(df)
        n_errors = 0
        if 'iter_status' in df.columns:
            n_errors = int((df['iter_status'] != 'converged').sum())

        lines.append(f'- **Time steps**: {n_steps}\n')
        lines.append(f'- **Solar Fraction**: {sf if isinstance(sf, str) else f"{sf:.2%}"}\n')
        lines.append(f'- **Solar Plant Factor**: {spf if isinstance(spf, str) else f"{spf:.2%}"}\n')
        lines.append(f'- **Convergence failures**: {n_errors} ({n_errors/n_steps*100:.1f}%)\n')
        lines.append(f'- **HTF**: {meta.get("HTF", "N/A")}\n')
        lines.append(f'- **Topology**: {meta.get("sim_args", {}).get("topology", "Parallel")}\n\n')
    else:
        lines.append('> ⚠️ Baseline CSV not found. Run Assessment 01.\n\n')

    # ─── Parametric summary ───────────────────────────────────────────
    lines.append('## 2. Parametric Sweep Results\n')
    sweep_csv = os.path.join(BASE_DIR, '02_parametric', 'parametric_sweep.csv')
    if os.path.exists(sweep_csv):
        df = pd.read_csv(sweep_csv)
        ok = df[df['Status'] == 'ok']
        failed = df[df['Status'] != 'ok']

        lines.append(f'- **Total runs**: {len(df)}\n')
        lines.append(f'- **Successful**: {len(ok)}\n')
        lines.append(f'- **Failed**: {len(failed)}\n\n')

        if not ok.empty:
            best_sf = ok.loc[ok['Solar Fraction'].idxmax()]
            best_lcoh = ok.loc[ok['LCOH ($/kWh)'].idxmin()]

            lines.append('### Best Solar Fraction\n')
            lines.append(f'- **Value**: {best_sf["Solar Fraction"]:.2%}\n')
            lines.append(f'- **Geometry**: D={best_sf["Tank diameter (m)"]:.1f} m, L={best_sf["Tank length (m)"]:.1f} m\n')
            lines.append(f'- **LCOH**: ${best_sf["LCOH ($/kWh)"]:.4f}/kWh\n\n')

            lines.append('### Lowest LCOH\n')
            lines.append(f'- **Value**: ${best_lcoh["LCOH ($/kWh)"]:.4f}/kWh\n')
            lines.append(f'- **Geometry**: D={best_lcoh["Tank diameter (m)"]:.1f} m, L={best_lcoh["Tank length (m)"]:.1f} m\n')
            lines.append(f'- **Solar Fraction**: {best_lcoh["Solar Fraction"]:.2%}\n\n')

            lines.append('### Full Results Table\n\n')
            lines.append(ok[['Tank diameter (m)', 'Tank length (m)', 'Solar Fraction',
                             'LCOH ($/kWh)', 'Tank Volume (m3)', 'N error steps']].to_markdown(index=False))
            lines.append('\n\n')
    else:
        lines.append('> ⚠️ Parametric sweep CSV not found. Run Assessment 02.\n\n')

    # ─── Error analysis summary ───────────────────────────────────────
    lines.append('## 3. Convergence Analysis\n')
    err_summary = os.path.join(BASE_DIR, '05_analysis', 'baseline_parallel', 'summary_overall.csv')
    if os.path.exists(err_summary):
        ds = pd.read_csv(err_summary)
        lines.append(ds.to_markdown(index=False))
        lines.append('\n\n')
    else:
        lines.append('> ⚠️ Error analysis not found. Run Assessment 05.\n\n')

    # ─── Figures reference ────────────────────────────────────────────
    lines.append('## 4. Key Figures\n\n')
    fig_dir = os.path.join(BASE_DIR, '06_figures')
    if os.path.exists(fig_dir):
        for f in sorted(os.listdir(fig_dir)):
            if f.endswith('.svg'):
                lines.append(f'### {f.replace("_", " ").replace(".svg", "").title()}\n')
                lines.append(f'![{f}](../06_figures/{f})\n\n')
    else:
        lines.append('> ⚠️ Figures not found. Run Assessment 06.\n\n')

    # ─── Write synthesis ──────────────────────────────────────────────
    synth_path = os.path.join(SYNTH_DIR, 'ARTICLE_SYNTHESIS.md')
    with open(synth_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f'✅ Synthesis written → {synth_path}')


if __name__ == '__main__':
    main()
