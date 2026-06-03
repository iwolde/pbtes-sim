import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbtes.analysis.results_reader import load_results
from pbtes.analysis.economics import EconomicAssessment

def main():
    if len(sys.argv) < 2:
        print("Usage: python scratch/calculate_lcoh.py <processed_results_file.csv>")
        sys.exit(1)
        
    filepath = sys.argv[1]
    
    df, meta = load_results(filepath)
    
    # Run Economic Assessment
    econ = EconomicAssessment(df, meta)
    res = econ.run_assessment()
    
    print("\n" + "="*50)
    print(" ECONOMIC PERFORMANCE ASSESSMENT")
    print(f" File: {os.path.basename(filepath)}")
    print("="*50)
    print(f"CAPEX PTC Field:       ${res['capex_ptc']:,.2f}")
    print(f"CAPEX TES System:      ${res['capex_tes']:,.2f}")
    print(f"CAPEX Pumps:           ${res['capex_pumps']:,.2f}")
    print(f"CAPEX Heat Exchangers: ${res['capex_hxs']:,.2f}")
    print(f"Total CAPEX:           ${res['capex_total']:,.2f}")
    print(f"Annualized CAPEX:      ${res['annualized_capex']:,.2f}/year")
    print("-"*50)
    print(f"Annual Electricity:    ${res['cost_electricity']:,.2f}/year")
    print(f"Annual Aux Fuel Cost:  ${res['cost_aux_fuel']:,.2f}/year")
    print(f"Annual O&M:            ${res['cost_om']:,.2f}/year")
    print(f"Total Annual OPEX:     ${res['opex_total']:,.2f}/year")
    print("-"*50)
    print(f"Total Energy Delivered: {res['q_delivered_MWh']:,.2f} MWh/year")
    print(f"Levelized Cost (LCOH):  ${res['lcoh_usd_per_MWh']:.2f}/MWh")
    print("="*50 + "\n")

if __name__ == '__main__':
    main()
