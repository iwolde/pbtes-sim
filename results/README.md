# Results Directory

Simulation results are stored here with descriptive filenames.

## Naming Convention

```
{tag}_{topology}_{tank_config}_{htf_tes}_D{diameter}_H{height}_A{aperture}_{days}d_{date}.csv
```

## Examples

```
baseline_Parallel_indirect_NaK_D7.0_H5.0_A1000_365d_20260520.csv
baseline_Series_direct_Air_D7.0_H5.0_A1000_365d_20260520.csv
sweep_Parallel_indirect_NaK_D4.0_H5.0_A1000_365d_20260520.csv
```

## CSV Format

Each CSV has a metadata header line: `# __meta__ = {JSON}`
Followed by standard CSV with all timestep data.

Use `pbtes.analysis.results_reader.load_results()` to read these files.
