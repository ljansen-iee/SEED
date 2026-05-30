"""
Compare old vs new workflow final energy demand results
"""

import pandas as pd
from pathlib import Path

def load_old_output(file_path: Path) -> pd.DataFrame:
    """Load old workflow output"""
    df = pd.read_csv(file_path)
    # Rename MA to Morocco, EG to Egypt, etc.
    country_mapping = {'MA': 'Morocco', 'EG': 'Egypt', 'ZA': 'South Africa', 'NAM': 'Namibia'}
    df['country'] = df['country'].map(country_mapping)
    return df

def load_new_output(file_path: Path) -> pd.DataFrame:
    """Load new workflow output"""
    return pd.read_csv(file_path)

def compare_sector_values(old_df: pd.DataFrame, new_df: pd.DataFrame, 
                          country: str, scenario: str, year: int, sector: str):
    """Compare values for a specific sector"""
    
    # Filter data
    old_filtered = old_df[
        (old_df['country'] == country) &
        (old_df['scenario'] == scenario) &
        (old_df['year'] == year)
    ][['carrier', sector]].copy()
    old_filtered.columns = ['carrier', 'old_value']
    
    new_filtered = new_df[
        (new_df['country'] == country) &
        (new_df['scenario'] == scenario) &
        (new_df['year'] == year)
    ][['carrier', sector]].copy()
    new_filtered.columns = ['carrier', 'new_value']
    
    # Merge
    comparison = pd.merge(old_filtered, new_filtered, on='carrier', how='outer').fillna(0)
    comparison['difference'] = comparison['new_value'] - comparison['old_value']
    comparison['ratio'] = comparison.apply(
        lambda row: row['new_value'] / row['old_value'] if row['old_value'] > 0 else 0, 
        axis=1
    )
    comparison['pct_diff'] = comparison.apply(
        lambda row: 100 * (row['new_value'] - row['old_value']) / row['old_value'] if row['old_value'] > 0 else 0,
        axis=1
    )
    
    return comparison

def main():
    base_dir = Path(__file__).parent / 'output_data'
    
    # Load data
    old_2030 = load_old_output(base_dir / 'industry_Optimistic_2030.csv')
    new_output = load_new_output(base_dir / 'CONFIG' / 'final_energy_demand_detailed_sectors_wide.csv')
    
    print("="*100)
    print("COMPARISON: OLD vs NEW WORKFLOW - Morocco Optimistic 2030")
    print("="*100)
    
    sectors_to_compare = [
        'iron and steel',
        'chemical and petrochemical',
        'non-metallic minerals',
        'paper pulp and print'
    ]
    
    for sector in sectors_to_compare:
        print(f"\n{'='*100}")
        print(f"SECTOR: {sector}")
        print("="*100)
        
        comparison = compare_sector_values(old_2030, new_output, 'Morocco', 'Optimistic', 2030, sector)
        
        # Only show carriers with non-zero values
        comparison_filtered = comparison[(comparison['old_value'] > 0) | (comparison['new_value'] > 0)]
        
        print(comparison_filtered.to_string(index=False))
        
        # Summary
        total_old = comparison_filtered['old_value'].sum()
        total_new = comparison_filtered['new_value'].sum()
        print(f"\nTOTAL: OLD={total_old:,.0f} MWh, NEW={total_new:,.0f} MWh, RATIO={total_new/total_old if total_old>0 else 0:.2f}x")

if __name__ == '__main__':
    main()
