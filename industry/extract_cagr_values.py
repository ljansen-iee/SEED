"""
Extract and save CAGR values from INDUSTRY_CONFIG.csv for easy reference.

This script creates CSV summaries of all CAGR values used in the model:
1. Production/Activity CAGR (volume growth)
2. Intensity CAGR (efficiency improvements)
3. Summary by sector and scenario

Output files in: industry/output_data/interim/cagr_extracts/
"""

from pathlib import Path
import pandas as pd

def extract_cagr_values():
    """Extract CAGR values from INDUSTRY_CONFIG.csv and save to readable CSVs."""
    
    base_dir = Path(__file__).parent
    config_path = base_dir / 'output_data' / 'CONFIG' / 'INDUSTRY_CONFIG.csv'
    output_dir = base_dir / 'output_data' / 'interim' / 'cagr_extracts'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*80)
    print("EXTRACTING CAGR VALUES FROM INDUSTRY_CONFIG.csv")
    print("="*80)
    
    # Load config
    df = pd.read_csv(config_path)
    cagr_rows = df[df['metric_2'] == 'cagr'].copy()
    
    print(f"\nTotal CAGR rows: {len(cagr_rows)}")
    
    # 1. Production CAGR
    production_cagr = cagr_rows[
        ~cagr_rows['metric_3'].str.contains('Energy intensity', na=False)
    ].copy()
    
    # Reshape for readability
    production_summary = []
    for _, row in production_cagr.iterrows():
        for country in ['Morocco', 'Egypt', 'South Africa', 'Namibia']:
            production_summary.append({
                'sector': row['metric_1'],
                'metric': row['metric_3'],
                'period': row['year'],
                'scenario': row['scenario'],
                'country': country,
                'cagr': row[country]
            })
    
    df_production = pd.DataFrame(production_summary)
    output_production = output_dir / 'production_cagr.csv'
    df_production.to_csv(output_production, index=False)
    print(f"\n[OK] Saved production CAGR: {output_production}")
    print(f"  Rows: {len(df_production)}")
    
    # 2. Intensity CAGR
    intensity_cagr = cagr_rows[
        cagr_rows['metric_3'].str.contains('Energy intensity', na=False)
    ].copy()
    
    # Reshape for readability
    intensity_summary = []
    for _, row in intensity_cagr.iterrows():
        for country in ['Morocco', 'Egypt', 'South Africa', 'Namibia']:
            intensity_summary.append({
                'sector': row['metric_1'],
                'technology_route': row['metric_3'],
                'period': row['year'],
                'scenario': row['scenario'],
                'country': country,
                'cagr': row[country]
            })
    
    df_intensity = pd.DataFrame(intensity_summary)
    output_intensity = output_dir / 'intensity_cagr.csv'
    df_intensity.to_csv(output_intensity, index=False)
    print(f"\n[OK] Saved intensity CAGR: {output_intensity}")
    print(f"  Rows: {len(df_intensity)}")
    
    # 3. Summary by sector and scenario (intensity only, unique values)
    intensity_pivot = intensity_cagr.groupby(
        ['metric_1', 'metric_3', 'scenario']
    )['Morocco'].first().reset_index()
    intensity_pivot = intensity_pivot.pivot(
        index=['metric_1', 'metric_3'],
        columns='scenario',
        values='Morocco'
    ).reset_index()
    
    output_summary = output_dir / 'intensity_cagr_summary.csv'
    intensity_pivot.to_csv(output_summary, index=False)
    print(f"\n[OK] Saved intensity CAGR summary: {output_summary}")
    print(f"  Rows: {len(intensity_pivot)}")
    
    # 4. Display summary table
    print("\n" + "="*80)
    print("INTENSITY CAGR SUMMARY (Efficiency Improvements)")
    print("="*80)
    print("\nValues are % per year (negative = improvement)")
    print("\n" + intensity_pivot.to_string(index=False))
    
    print("\n" + "="*80)
    print("SIMPLE SECTORS (Not in CONFIG - Computed Dynamically)")
    print("="*80)
    print("""
Simple sectors use UNSD historical CAGR (activity) + scenario-based efficiency rates:

Activity Multipliers:
  - BAU:        1.0× (historical trend)
  - Progressive: 1.2× (20% faster)
  - Optimistic:  1.5× (50% faster)

Efficiency Rates (per year):
  - BAU:        -1.0%
  - Progressive: -2.0%
  - Optimistic:  -3.0%

Sectors: Food & tobacco, Construction, Machinery, Mining & quarrying, 
         Non-ferrous metals, Textile & leather, Transport equipment, 
         Wood & wood products

[!] TODO: Validate these placeholder values against sector-specific studies
""")
    
    print("\n" + "="*80)
    print("EXTRACTION COMPLETE!")
    print("="*80)
    print(f"\nOutput directory: {output_dir}")
    print("\nGenerated files:")
    print("  1. production_cagr.csv         - Production/volume growth rates")
    print("  2. intensity_cagr.csv          - Energy intensity improvements")
    print("  3. intensity_cagr_summary.csv  - Summary table by scenario")
    print("\nSee also: docs/CAGR_SUMMARY.md for full methodology documentation")


if __name__ == '__main__':
    extract_cagr_values()
