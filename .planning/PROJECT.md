# Project

## What This Is
A robust, automated simulation and parametric analysis pipeline for evaluating the PBTES (Packed Bed Thermal Energy Storage) concept for high-temperature industrial solar heat applied to zinc galvanizing.

## Core Value
To provide accurate, convergence-stable data (temperatures, metrics, economics) using NaK (primary) and Air (comparison) as HTFs for a Q1 academic article, eliminating current codebase instabilities and manual workflows.

## Key Decisions
| Decision | Rationale | Outcome |
|----------|-----------|---------|
| HTF: NaK (primary), Air (comparison) | NaK available in CoolProp, appropriate for 300-600 C; Air for low-cost reference | Good |
| Refactor First | Core engine had 136 bare exceptions and 0% test coverage; parametric sweeps require 98%+ convergence stability | Good |
| Pressure / Pump | Try to include pressure with NaK, fallback to mass-flow post-processing if convergence fails | Good |
| Control Logic | Evolve beyond simple temperature limits to maximize solar fraction | Good |
| Automated Sweeps | Manual runs are too slow for an academic article's parametric analysis | Good |
| Simple LCOH | A Levelized Cost of Heat based on CAPEX/OPEX is sufficient for the article | Good |
| Extract Network Modes | Refactor 6 duplicated create_network methods into a single parameterized method | Good |
| Parallel/Series | Support both Series and Parallel configurations cleanly with Pipe components | Good |
| Zinc pool always ON | Dynamic demand is core novelty; fixed-demand mode retained for testing | Good |

## Current Milestone: v1.2 Publication Pipeline

**Goal:** Complete convergence fixes (Phase C), then generate all publication results (Phase D).

**Target features:**
- Fix Mode 1 offdesign convergence for NaK
- Fix Mode 6 design ("too many parameters")
- Converge all 6 modes for all 4 topologies
- Run 365-day simulations for all configurations
- Run parametric sweeps (aperture, TES volume, topology)
- Generate 13+ publication figures
- Compute LCOH and exergoeconomic analysis
- Draft paper

## Requirements

### Completed
- CORE-01: Refactor simulation to eliminate bare exceptions and loud failures -- v1.0
- CORE-02: Map thermodynamic boundaries to achieve solver convergence -- v1.0
- CORE-03: Improve control logic to maximize solar fraction and minimize auxiliary heat -- v1.0
- ARCH-01: Support existing Parallel configuration cleanly -- v1.0
- ARCH-02: Implement Series integration configuration -- v1.0
- ARCH-03: Dual HTF support (NaK + Air) with heat exchanger coupling -- v1.0
- METRICS-01: Calculate pump power (pressure modeling or mass-flow fallback) -- v1.0
- ANALYSIS-01: Implement automated parametric sweep script -- v1.0
- ANALYSIS-02: Produce publication-quality graphs -- v1.0
- ANALYSIS-03: Formulate narrative for the scientific article based on results -- v1.0
- ECON-01: Implement Simple LCOH economic model -- v1.0
- CONF-01: Validate parallel vs series topological connections mathematically -- v1.1
- CONF-02: Ensure mode transitions explicitly cover mass flow routing conditions -- v1.1
- PHYS-01: Validate CoolProp constraint limits against NaK boundaries -- v1.1
- PHYS-02: Ensure analytical energy balances hold (1st and 2nd law) -- v1.1
- PHYS-03: Validate mathematical suppositions and control logic in code -- v1.1
- TEST-01: Implement automated unit tests for single operation modes using pytest -- v1.1
- TEST-02: Implement integration tests running transient scenarios -- v1.1
- TEST-03: Run testing scripts to assess advances and identify gaps -- v1.1

### Active
See `.planning/REQUIREMENTS.md` and `TODO.md` for Phase C and D requirements.

### Out of Scope
- [Detailed Financial Model] -- Simple LCOH is sufficient for the scope of the article
- [Weather-based predictive control logic] -- Explicitly deferred to avoid forecasting complexity for this article

## Context

Shipped v1.1 Robust Physics and Testing Framework.
The simulation engine is now backed by comprehensive pytest suites.
Fundamental physics boundaries (NaK limits) and explicit 1st and 2nd law energy balances are analytically verified.
An exhaustive NxN dynamic mode transition test ensures that changing between any active state correctly routes mass flows.
Codebase now in maintenance/improvement phase for convergence hardening.

## Evolution

This document evolves at phase transitions and milestone boundaries.

- Last updated: 2026-05-21 after documentation coherence audit