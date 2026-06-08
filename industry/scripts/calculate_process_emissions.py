"""
Calculate industrial process emissions from production volumes and emission factors.

Process emissions are NON-ENERGY CO₂ emissions from chemical/physical reactions:
- Steel: Carbon in blast furnace reactions with iron ore
- Cement: Calcination (CaCO₃ → CaO + CO₂)
- HVC: Fossil feedstock carbon
- Aluminium: Anode oxidation in electrolysis

Formula:
    MtCO₂/year = Σ_route [emission_factor(tCO₂/t) × production_route(Mt/year)]

Emission factors are from JRC-IDEES EU28 average (future best-case), FIXED over time.

Input:
    - INDUSTRY_CONFIG.csv: Production volumes by route, country, scenario, year
    
Output:
    - process_emissions.csv: Long format [country, scenario, year, sector, route, MtCO2]
    - process_emissions_summary.csv: Aggregated by sector
"""

from pathlib import Path
import pandas as pd
import numpy as np
from typing import Optional
from industry.utils.process_emission_factors import get_emission_factor, PROCESS_EMISSION_FACTORS


class ProcessEmissionCalculator:
    """Calculate process emissions from production data."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize calculator with INDUSTRY_CONFIG.csv.
        
        Args:
            config_path: Path to INDUSTRY_CONFIG.csv. If None, uses default location.
        """
        if config_path is None:
            industry_dir = Path(__file__).resolve().parents[1]  # Go up from scripts/ to industry/
            config_path = industry_dir / "output_data" / "CONFIG" / "INDUSTRY_CONFIG.csv"
        
        print(f"Loading configuration from: {config_path}")
        self.config = pd.read_csv(config_path)
        print(f"✓ Loaded {len(self.config)} rows")
        
        # Get available countries from config columns
        self.countries = [col for col in self.config.columns 
                         if col not in ['metric_1', 'metric_2', 'metric_3', 'metric_4', 
                                       'year', 'scenario', 'units']]
        print(f"✓ Countries: {self.countries}")
    
    def calculate_steel_emissions(self, years: list, scenarios: list) -> pd.DataFrame:
        """
        Calculate process emissions for steel production by route.
        
        Steel production is calculated as:
        1. Get total steel production (metric_3='Steel production per year')
        2. Get technology route shares (metric_2='technology_route')
        3. Split production by route
        4. Apply route-specific emission factors
        
        Steel routes have different emission factors:
        - BF+BOF (blast furnace): 0.22 tCO₂/t steel
        - DR+EAF (direct reduction): 0.05 tCO₂/t steel
        - EAF (electric arc): 0.05 tCO₂/t steel
        
        Args:
            years: Target years (e.g., [2030, 2035, 2040, 2045, 2050])
            scenarios: Scenarios (e.g., ['BAU', 'Progressive', 'Optimistic'])
        
        Returns:
            DataFrame with columns: country, scenario, year, sector, route, production_Mt, factor_tCO2_per_t, emissions_MtCO2
        """
        print("\nCalculating steel process emissions...")
        
        # Get total steel production data (lowercase after standardization)
        steel_total = self.config[
            (self.config['metric_1'] == 'iron and steel') &
            (self.config['metric_2'] == 'production') &
            (self.config['metric_3'] == 'steel production per year')
        ].copy()
        
        if steel_total.empty:
            print("  Warning: No steel production data found")
            return pd.DataFrame()
        
        # Get technology route shares
        steel_routes = self.config[
            (self.config['metric_1'] == 'iron and steel') &
            (self.config['metric_2'] == 'technology_route')
        ].copy()
        
        if steel_routes.empty:
            print("  Warning: No steel route share data found")
            return pd.DataFrame()
        
        results = []
        
        # For each total production row, calculate route-specific production
        for _, prod_row in steel_total.iterrows():
            year = int(prod_row['year'])
            scenario = prod_row['scenario']
            
            if year not in years or scenario not in scenarios:
                continue
            
            # Get route shares for this year/scenario
            route_shares = steel_routes[
                (steel_routes['year'] == str(year)) &
                (steel_routes['scenario'] == scenario)
            ]
            
            for country in self.countries:
                total_production_100t = prod_row[country]
                if pd.isna(total_production_100t) or total_production_100t == 0:
                    continue
                
                # Convert 100 tonnes → Mt
                total_production_mt = total_production_100t * 100 / 1e6
                
                # Split by route
                for _, route_row in route_shares.iterrows():
                    route = route_row['metric_3']
                    route_share = route_row[country]
                    
                    if pd.isna(route_share) or route_share == 0:
                        continue
                    
                    # Route-specific production
                    route_production_mt = total_production_mt * route_share
                    
                    # Get emission factor
                    emission_factor = get_emission_factor('iron and steel', route)
                    
                    # Calculate emissions: Mt/year × tCO₂/t = MtCO₂/year
                    emissions_mt = route_production_mt * emission_factor
                    
                    results.append({
                        'country': country,
                        'scenario': scenario,
                        'year': year,
                        'sector': 'iron and steel',
                        'route': route,
                        'production_Mt': route_production_mt,
                        'factor_tCO2_per_t': emission_factor,
                        'emissions_MtCO2': emissions_mt
                    })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} emission records")
            print(f"  Total emissions range: {df['emissions_MtCO2'].sum():.2f} MtCO₂ (across all scenarios/years)")
        
        return df
    
    def calculate_cement_emissions(self, years: list, scenarios: list) -> pd.DataFrame:
        """
        Calculate process emissions for cement production.
        
        Cement has fixed emission factor: 0.54 tCO₂/t clinker (from calcination)
        
        Args:
            years: Target years
            scenarios: Scenarios
        
        Returns:
            DataFrame with emissions data
        """
        print("\nCalculating cement process emissions...")
        
        # Get cement production data (lowercase after standardization)
        cement_prod = self.config[
            (self.config['metric_1'] == 'non-metallic minerals') &
            (self.config['metric_2'] == 'production') &
            (self.config['metric_3'] == 'cement production per year')
        ].copy()
        
        if cement_prod.empty:
            print("  Warning: No cement production data found")
            return pd.DataFrame()
        
        emission_factor = get_emission_factor('non-metallic minerals', 'Cement')
        
        results = []
        for _, row in cement_prod.iterrows():
            year = int(row['year'])
            scenario = row['scenario']
            
            if year not in years or scenario not in scenarios:
                continue
            
            for country in self.countries:
                production_100t = row[country]
                if pd.isna(production_100t) or production_100t == 0:
                    continue
                
                # Convert 100 tonnes → Mt
                production_mt = production_100t * 100 / 1e6
                
                # Calculate emissions
                emissions_mt = production_mt * emission_factor
                
                results.append({
                    'country': country,
                    'scenario': scenario,
                    'year': year,
                    'sector': 'non-metallic minerals',
                    'route': 'Cement',
                    'production_Mt': production_mt,
                    'factor_tCO2_per_t': emission_factor,
                    'emissions_MtCO2': emissions_mt
                })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} emission records")
            print(f"  Total emissions range: {df['emissions_MtCO2'].sum():.2f} MtCO₂")
        
        return df
    
    def calculate_hvc_emissions(self, years: list, scenarios: list) -> pd.DataFrame:
        """
        Calculate process emissions for HVC (High Value Chemicals) production.
        
        HVC emission factors:
        - Primary (steam cracking): 0.18 tCO₂/t HVC
        - From feedstock: 0.23 tCO₂/t HVC
        - Recycling routes: 0.0 tCO₂/t HVC
        
        Args:
            years: Target years
            scenarios: Scenarios
        
        Returns:
            DataFrame with emissions data
        """
        print("\nCalculating HVC process emissions...")
        
        # Get HVC production data (lowercase after standardization)
        hvc_prod = self.config[
            (self.config['metric_1'] == 'chemical and petrochemical') &
            (self.config['metric_2'] == 'production') &
            (self.config['metric_3'] == 'hvc production per year')
        ].copy()
        
        if hvc_prod.empty:
            print("  Warning: No HVC production data found")
            return pd.DataFrame()
        
        # For now, use 'HVC_primary' emission factor
        # TODO: Differentiate by pathway when pathway-specific production is available
        emission_factor = get_emission_factor('chemical and petrochemical', 'HVC_primary')
        
        results = []
        for _, row in hvc_prod.iterrows():
            year = int(row['year'])
            scenario = row['scenario']
            
            if year not in years or scenario not in scenarios:
                continue
            
            for country in self.countries:
                production_100t = row[country]
                if pd.isna(production_100t) or production_100t == 0:
                    continue
                
                # Convert 100 tonnes → Mt
                production_mt = production_100t * 100 / 1e6
                
                # Calculate emissions
                emissions_mt = production_mt * emission_factor
                
                results.append({
                    'country': country,
                    'scenario': scenario,
                    'year': year,
                    'sector': 'chemical and petrochemical',
                    'route': 'HVC_primary',
                    'production_Mt': production_mt,
                    'factor_tCO2_per_t': emission_factor,
                    'emissions_MtCO2': emissions_mt
                })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} emission records")
            print(f"  Total emissions range: {df['emissions_MtCO2'].sum():.2f} MtCO₂")
        
        return df
    
    def calculate_ammonia_emissions(self, years: list, scenarios: list) -> pd.DataFrame:
        """
        Calculate process emissions for ammonia production.
        
        Ammonia has NO process emissions (emissions are on energy side from H₂ production).
        Returns rows with 0 emissions for traceability (not empty DataFrame).
        
        Args:
            years: Target years
            scenarios: Scenarios
        
        Returns:
            DataFrame with 0 emissions (for completeness in output CSV)
        """
        print("\nAmmonia process emissions: 0 (emissions on energy side)")
        
        # Get ammonia production data from chemical and petrochemical sector
        ammonia_prod = self.config[
            (self.config['metric_1'] == 'chemical and petrochemical') &
            (self.config['metric_2'] == 'production') &
            (self.config['metric_3'] == 'ammonia production per year')
        ].copy()
        
        if ammonia_prod.empty:
            print("  No ammonia production data found")
            return pd.DataFrame()
        
        results = []
        
        for _, row in ammonia_prod.iterrows():
            year = int(row['year'])
            scenario = row['scenario']
            
            if year not in years or scenario not in scenarios:
                continue
            
            for country in self.countries:
                production_100t = row[country]
                if pd.isna(production_100t) or production_100t == 0:
                    continue
                
                # Convert to Mt
                production_mt = production_100t * 100 / 1e6
                
                # Append row with 0 emissions (for traceability)
                results.append({
                    'country': country,
                    'scenario': scenario,
                    'year': year,
                    'sector': 'chemical and petrochemical',
                    'route': 'ammonia (no process emissions)',
                    'production_Mt': production_mt,
                    'factor_tCO2_per_t': 0.0,
                    'emissions_MtCO2': 0.0
                })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} rows (all with 0 emissions for traceability)")
        
        return df
    
    def calculate_paper_emissions(self, years: list, scenarios: list) -> pd.DataFrame:
        """
        Calculate process emissions for paper/pulp production.
        
        Paper has minor process emissions:
        - Pulp: 0.02 tCO₂/t (from pulping chemicals)
        - Paper: 0.01 tCO₂/t (very minor)
        
        Args:
            years: Target years
            scenarios: Scenarios
        
        Returns:
            DataFrame with emissions data
        """
        print("\nCalculating paper/pulp process emissions...")
        
        # Get pulp production (lowercase after standardization)
        pulp_prod = self.config[
            (self.config['metric_1'] == 'paper, pulp and printing') &
            (self.config['metric_2'] == 'production') &
            (self.config['metric_3'] == 'pulp production per year')
        ].copy()
        
        # Get paper production (lowercase after standardization)
        paper_prod = self.config[
            (self.config['metric_1'] == 'paper, pulp and printing') &
            (self.config['metric_2'] == 'production') &
            (self.config['metric_3'] == 'paper production per year')
        ].copy()
        
        results = []
        
        # Process pulp emissions
        if not pulp_prod.empty:
            emission_factor = get_emission_factor('paper, pulp and printing', 'Pulp')
            for _, row in pulp_prod.iterrows():
                year = int(row['year'])
                scenario = row['scenario']
                
                if year not in years or scenario not in scenarios:
                    continue
                
                for country in self.countries:
                    production_100t = row[country]
                    if pd.isna(production_100t) or production_100t == 0:
                        continue
                    
                    production_mt = production_100t * 100 / 1e6
                    emissions_mt = production_mt * emission_factor
                    
                    results.append({
                        'country': country,
                        'scenario': scenario,
                        'year': year,
                        'sector': 'paper, pulp and printing',
                        'route': 'Pulp',
                        'production_Mt': production_mt,
                        'factor_tCO2_per_t': emission_factor,
                        'emissions_MtCO2': emissions_mt
                    })
        
        # Process paper emissions
        if not paper_prod.empty:
            emission_factor = get_emission_factor('paper, pulp and printing', 'Paper')
            for _, row in paper_prod.iterrows():
                year = int(row['year'])
                scenario = row['scenario']
                
                if year not in years or scenario not in scenarios:
                    continue
                
                for country in self.countries:
                    production_100t = row[country]
                    if pd.isna(production_100t) or production_100t == 0:
                        continue
                    
                    production_mt = production_100t * 100 / 1e6
                    emissions_mt = production_mt * emission_factor
                    
                    results.append({
                        'country': country,
                        'scenario': scenario,
                        'year': year,
                        'sector': 'paper, pulp and printing',
                        'route': 'Paper',
                        'production_Mt': production_mt,
                        'factor_tCO2_per_t': emission_factor,
                        'emissions_MtCO2': emissions_mt
                    })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} emission records")
            print(f"  Total emissions range: {df['emissions_MtCO2'].sum():.2f} MtCO₂")
        else:
            print("  Warning: No paper/pulp production data found")
        
        return df
    
    def calculate_aluminium_emissions(self, years: list, scenarios: list) -> pd.DataFrame:
        """
        Calculate process emissions for aluminium production.
        
        Aluminium process emissions come from anode oxidation in Hall-Héroult electrolysis:
        - Primary aluminium: 1.5 tCO₂/t (carbon anode → CO₂)
        - Secondary aluminium: 0.0 tCO₂/t (recycling - no chemical reaction)
        
        Emission factors from PROCESS_EMISSION_FACTORS['non-ferrous metals']:
        - 'Aluminium_primary': 1.5 tCO₂/t
        - 'Aluminium_secondary': 0.0 tCO₂/t
        
        Args:
            years: Target years
            scenarios: Scenarios
        
        Returns:
            DataFrame with emissions data by route
        """
        print("\nCalculating aluminium process emissions...")
        
        # Get aluminium production data (lowercase after standardization)
        aluminium_prod = self.config[
            (self.config['metric_1'] == 'non-ferrous metals') &
            (self.config['metric_2'] == 'production') &
            (self.config['metric_3'] == 'aluminium production per year')
        ].copy()
        
        if aluminium_prod.empty:
            print("  Warning: No aluminium production data found")
            return pd.DataFrame()
        
        # Get technology route shares
        aluminium_routes = self.config[
            (self.config['metric_1'] == 'non-ferrous metals') &
            (self.config['metric_2'] == 'technology_route')
        ].copy()
        
        if aluminium_routes.empty:
            print("  Warning: No aluminium route share data found")
            return pd.DataFrame()
        
        results = []
        
        # For each production row, calculate route-specific emissions
        for _, prod_row in aluminium_prod.iterrows():
            year = int(prod_row['year'])
            scenario = prod_row['scenario']
            
            if year not in years or scenario not in scenarios:
                continue
            
            # Get route shares for this year/scenario
            route_shares = aluminium_routes[
                (aluminium_routes['year'] == str(year)) &
                (aluminium_routes['scenario'] == scenario)
            ]
            
            for country in self.countries:
                total_production_100t = prod_row[country]
                if pd.isna(total_production_100t) or total_production_100t == 0:
                    continue
                
                # Convert 100 tonnes → Mt
                total_production_mt = total_production_100t * 100 / 1e6
                
                # Split by route
                for _, route_row in route_shares.iterrows():
                    route = route_row['metric_3']  # e.g., 'Primary aluminium', 'Secondary aluminium'
                    route_share = route_row[country]
                    
                    if pd.isna(route_share) or route_share == 0:
                        continue
                    
                    # Route-specific production
                    route_production_mt = total_production_mt * route_share
                    
                    # Get emission factor (map route name to factor key - lowercase after standardization)
                    if 'primary' in route.lower():
                        emission_factor = get_emission_factor('non-ferrous metals', 'Aluminium_primary')
                    elif 'secondary' in route.lower():
                        emission_factor = get_emission_factor('non-ferrous metals', 'Aluminium_secondary')
                    else:
                        emission_factor = get_emission_factor('non-ferrous metals', 'Unspecified')
                    
                    # Calculate emissions: Mt/year × tCO₂/t = MtCO₂/year
                    emissions_mt = route_production_mt * emission_factor
                    
                    results.append({
                        'country': country,
                        'scenario': scenario,
                        'year': year,
                        'sector': 'non-ferrous metals',
                        'route': route,
                        'production_Mt': route_production_mt,
                        'factor_tCO2_per_t': emission_factor,
                        'emissions_MtCO2': emissions_mt
                    })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} emission records")
            
            # Summary by route
            primary_emissions = df[df['route'].str.contains('Primary', na=False)]['emissions_MtCO2'].sum()
            secondary_emissions = df[df['route'].str.contains('Secondary', na=False)]['emissions_MtCO2'].sum()
            
            print(f"  Primary aluminium: {primary_emissions:.2f} MtCO₂ (across all scenarios/years)")
            print(f"  Secondary aluminium: {secondary_emissions:.2f} MtCO₂ (should be ~0)")
            print(f"  Total: {df['emissions_MtCO2'].sum():.2f} MtCO₂")
        
        return df
    
    def calculate_generic_sector_emissions(self, 
                                          sector_name: str,
                                          production_metric: str,
                                          route_name: str,
                                          years: list, 
                                          scenarios: list) -> pd.DataFrame:
        """
        Generic method to calculate process emissions for any sector with production data.
        
        This modular approach allows easy addition of new sectors as production data
        becomes available.
        
        Args:
            sector_name: Sector name from CONFIG metric_1 (e.g., 'non-ferrous metals')
            production_metric: Production metric from CONFIG metric_3 (e.g., 'Aluminium production per year')
            route_name: Route name for emission factor lookup (e.g., 'Aluminium_primary')
            years: Target years
            scenarios: Scenarios
        
        Returns:
            DataFrame with emissions data
        
        Example:
            # When aluminium production data becomes available:
            aluminium_df = calc.calculate_generic_sector_emissions(
                sector_name='non-ferrous metals',
                production_metric='Aluminium production per year',
                route_name='Aluminium_primary',
                years=[2030, 2040, 2050],
                scenarios=['BAU']
            )
        """
        print(f"\nCalculating {sector_name} ({route_name}) process emissions...")
        
        # Get production data
        production = self.config[
            (self.config['metric_1'] == sector_name) &
            (self.config['metric_2'] == 'production') &
            (self.config['metric_3'] == production_metric)
        ].copy()
        
        if production.empty:
            print(f"  Warning: No production data found for {production_metric}")
            return pd.DataFrame()
        
        emission_factor = get_emission_factor(sector_name, route_name)
        
        if emission_factor == 0.0:
            print(f"  Info: Emission factor is 0.0 for {route_name}")
            return pd.DataFrame()
        
        results = []
        for _, row in production.iterrows():
            year = int(row['year'])
            scenario = row['scenario']
            
            if year not in years or scenario not in scenarios:
                continue
            
            for country in self.countries:
                production_100t = row[country]
                if pd.isna(production_100t) or production_100t == 0:
                    continue
                
                production_mt = production_100t * 100 / 1e6
                emissions_mt = production_mt * emission_factor
                
                results.append({
                    'country': country,
                    'scenario': scenario,
                    'year': year,
                    'sector': sector_name,
                    'route': route_name,
                    'production_Mt': production_mt,
                    'factor_tCO2_per_t': emission_factor,
                    'emissions_MtCO2': emissions_mt
                })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} emission records")
            print(f"  Total emissions: {df['emissions_MtCO2'].sum():.2f} MtCO₂")
        
        return df
    
    def calculate_all_emissions(self, 
                                years: list = [2030, 2035, 2040, 2045, 2050],
                                scenarios: list = ['BAU', 'Progressive', 'Optimistic']) -> pd.DataFrame:
        """
        Calculate all process emissions for sectors with non-zero emission factors.
        
        Args:
            years: Target years
            scenarios: Scenarios
        
        Returns:
            Combined DataFrame with all emissions
        """
        print("\n" + "="*80)
        print("CALCULATING PROCESS EMISSIONS")
        print("="*80)
        
        all_emissions = []
        
        # Steel (by route)
        steel_df = self.calculate_steel_emissions(years, scenarios)
        if not steel_df.empty:
            all_emissions.append(steel_df)
        
        # Cement
        cement_df = self.calculate_cement_emissions(years, scenarios)
        if not cement_df.empty:
            all_emissions.append(cement_df)
        
        # HVC (chemicals)
        hvc_df = self.calculate_hvc_emissions(years, scenarios)
        if not hvc_df.empty:
            all_emissions.append(hvc_df)
        
        # Ammonia (zero emissions - rows for traceability)
        ammonia_df = self.calculate_ammonia_emissions(years, scenarios)
        if not ammonia_df.empty:
            all_emissions.append(ammonia_df)
        
        # Paper/Pulp (minor emissions)
        paper_df = self.calculate_paper_emissions(years, scenarios)
        if not paper_df.empty:
            all_emissions.append(paper_df)
        
        # Aluminium (by route: Primary has emissions, Secondary has zero)
        aluminium_df = self.calculate_aluminium_emissions(years, scenarios)
        if not aluminium_df.empty:
            all_emissions.append(aluminium_df)
        
        # TODO: Additional sectors when production volumes become available:
        # - Ceramics: Use calculate_generic_sector_emissions() with 'Ceramics' (0.03 tCO2/t)
        # - Glass: Use calculate_generic_sector_emissions() with 'Glass' (0.02 tCO2/t)
        # - Food processing: Meat (fermentation), dairy products if data available
        
        if not all_emissions:
            print("\nWarning: No emissions calculated!")
            return pd.DataFrame()
        
        # Combine all sectors
        combined = pd.concat(all_emissions, ignore_index=True)
        
        print(f"\n" + "="*80)
        print(f"TOTAL: {len(combined)} emission records")
        print(f"TOTAL EMISSIONS: {combined['emissions_MtCO2'].sum():.2f} MtCO₂ (all scenarios/years)")
        print("="*80)
        
        return combined


def main():
    """Main execution workflow."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Calculate industrial process emissions')
    parser.add_argument('--config', type=str, help='Path to INDUSTRY_CONFIG.csv')
    parser.add_argument('--output-dir', type=str, help='Output directory for results')
    args = parser.parse_args()
    
    # Initialize calculator
    calc = ProcessEmissionCalculator(config_path=args.config if args.config else None)
    
    # Calculate emissions
    emissions_df = calc.calculate_all_emissions()
    
    if emissions_df.empty:
        print("No emissions to save.")
        return
    
    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        # Default to industry/output_data/interim_data/
        industry_root = Path(__file__).resolve().parents[1]  # Go up from scripts/ to industry/
        output_dir = industry_root / "output_data" / "interim_data"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save detailed emissions (long format)
    output_long = output_dir / "process_emissions.csv"
    emissions_df.to_csv(output_long, index=False)
    print(f"\n✓ Saved detailed emissions: {output_long}")
    
    # Save summary by sector/scenario/year
    summary = emissions_df.groupby(
        ['country', 'sector', 'scenario', 'year'], 
        as_index=False
    )['emissions_MtCO2'].sum()
    
    output_summary = output_dir / "process_emissions_summary.csv"
    summary.to_csv(output_summary, index=False)
    print(f"✓ Saved summary: {output_summary}")
    
    # Print summary table
    print("\n" + "="*80)
    print("EMISSIONS SUMMARY BY SECTOR")
    print("="*80)
    sector_summary = emissions_df.groupby('sector')['emissions_MtCO2'].sum().sort_values(ascending=False)
    for sector, emissions in sector_summary.items():
        print(f"  {sector:30s}: {emissions:10.2f} MtCO₂")
    
    print("\n" + "="*80)
    print("✓ Process emissions calculation complete")
    print("="*80)


if __name__ == "__main__":
    main()
