# Parametric Analysis Synthesis

## Overview
This document synthesizes the results of the parametric sweep for the PBTES system, evaluating the trade-offs between tank geometry, solar fraction, and Levelized Cost of Heat (LCOH).

## Key Metrics
- **Lowest LCOH**: $0.0650/kWh
  - Achieved with Tank Diameter: 5.00 m, Tank Length: 5.00 m
  - Corresponding Solar Fraction: 65.00%
- **Highest Solar Fraction**: 95.00%
  - Achieved with Tank Diameter: 10.00 m, Tank Length: 9.50 m
  - Corresponding LCOH: $0.0950/kWh

## Visualizations

### LCOH vs Tank Volume
![LCOH vs Volume](figures/lcoh_vs_volume.svg)

This plot illustrates the relationship between the tank volume and the resulting LCOH, colored by the solar fraction. It highlights the economic sweet spots where optimal solar fraction intersects with cost-effective storage sizing.

### Solar Fraction Matrix
![Solar Fraction Matrix](figures/solar_fraction_matrix.svg)

This figure shows how the combination of tank diameter and length impacts the overall solar fraction of the system, providing guidance on geometrical design constraints.

## Conclusion
The parametric analysis demonstrates that using Molten Salt as a unified HTF can achieve stable and cost-effective thermal energy storage. The optimal dimensions provide a clear pathway for designing pilot-scale facilities while maximizing solar energy utilization.
