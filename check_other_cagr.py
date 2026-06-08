import sys
sys.path.append('industry/scripts')
from calculate_final_energy_demand import get_final_energy_cagr_from_unsd

countries = ['Morocco', 'Egypt', 'South Africa', 'Namibia']

print('\n' + '='*80)
print('CHECKING CAGR VALUES USED IN CALCULATION')
print('='*80)

for country in countries:
    print(f'\n{country}:')
    
    # Get the CAGR that the calculation script is using
    cagr = get_final_energy_cagr_from_unsd(country, 'Industry n.e.s')
    
    print(f'  Historical CAGR from calc script: {cagr*100:.2f}%/year')
    
    # Show what this becomes with scenario multipliers
    print(f'\n  Applied in scenarios:')
    print(f'    BAU: {cagr*100:.2f}% activity growth + {-1.0:.1f}% efficiency = {(cagr-0.01)*100:.2f}% total')
    print(f'    Progressive: {cagr*1.2*100:.2f}% activity growth + {-2.0:.1f}% efficiency = {(cagr*1.2-0.02)*100:.2f}% total')
    print(f'    Optimistic: {cagr*1.5*100:.2f}% activity growth + {-3.0:.1f}% efficiency = {(cagr*1.5-0.03)*100:.2f}% total')
    
    # Calculate what 2030 energy would be starting from UNSD 2020
    print(f'\n  Projected 2030 with BAU formula:')
    
    # Need to get base 2020 value
    import pandas as pd
    from pathlib import Path
    
    unsd_file = f'data/country_specific/UNSD_{country}-2020.csv'
    df = pd.read_csv(unsd_file)
    sector_col = 'Transactions(down)/Commodity(right)'
    energy_col = 'Total Energy'
    nes_row = df[df[sector_col].str.contains('Industry n.e.s', case=False, na=False, regex=True)]
    
    if not nes_row.empty:
        energy_val = nes_row[energy_col].iloc[0]
        if isinstance(energy_val, str):
            energy_val = energy_val.replace('*', '').replace('---', '0').strip()
        base_2020_gwh = float(energy_val)
        
        # Apply BAU formula: Base × Activity_Growth × Efficiency_Change
        years_elapsed = 10
        activity_factor = (1 + cagr) ** years_elapsed
        efficiency_factor = (1 + (-0.01)) ** years_elapsed  # -1% efficiency
        
        projected_2030 = base_2020_gwh * activity_factor * efficiency_factor
        
        print(f'    Base 2020: {base_2020_gwh:,.1f} GWh')
        print(f'    Activity factor (10 years): {activity_factor:.4f}')
        print(f'    Efficiency factor (10 years): {efficiency_factor:.4f}')
        print(f'    Projected 2030: {projected_2030:,.1f} GWh')

print('\n' + '='*80)
