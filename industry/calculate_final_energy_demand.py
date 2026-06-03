"""
Calculate final energy demand from INDUSTRY_CONFIG.csv

Implements hierarchical steel calculation, endogenous demands for ammonia and steel,
and proper chemical sector aggregation (ammonia + HVC).
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import warnings

warnings.filterwarnings('ignore')

# Define carrier order
CARRIER_ORDER = ['oil', 'gas', 'electricity', 'coal', 'heat', 'biomass', 
                 'hydrogen', 'ammonia', 'methanol', 'steel']

# Map INDUSTRY_CONFIG metric_1 names to output column names
SECTOR_NAME_MAPPING = {
    'iron and steel': 'iron and steel',
    'ammonia': 'chemical and petrochemical',
    'chemical and petrochemical': 'chemical and petrochemical',
    'non-metallic minerals': 'non-metallic minerals',
    'paper, pulp and printing': 'paper pulp and print',
    'food and tobacco': 'food and tobacco',
    'machinery': 'machinery',
    'Manufacturing  const. and mining': 'construction',
    'mining and quarrying': 'mining and quarrying',
    'non-ferrous metals': 'non-ferrous metals',
    'textile and leather': 'textile and leather',
    'transport equipment': 'transport equipment',
    'wood and wood products': 'wood and wood products'
}

# Fuel name mapping
FUEL_MAPPING = {
    'diesel': 'oil',
    'oil': 'oil',
    'natural_gas': 'gas',
    'gas': 'gas',
    'electricity': 'electricity',
    'coal': 'coal',
    'heat': 'heat',
    'biomass': 'biomass',
    'hydrogen': 'hydrogen',
    'ammonia': 'ammonia',
    'methanol': 'methanol',
    'steel': 'steel',
    'naphtha': 'oil',  # HVC fuel
    'LPG': 'gas',      # HVC fuel
}

# Ammonia LHV conversion (MWh per tonne)
AMMONIA_LHV = 5.17  # MWh/tonne


class FinalEnergyCalculator:
    """Calculate final energy demand from INDUSTRY_CONFIG.csv"""
    
    def __init__(self, config_path: Path, interim_dir: Path):
        self.config_path = config_path
        self.interim_dir = interim_dir
        
        print(f"Loading configuration from {config_path}...")
        self.config = pd.read_csv(config_path)
        print(f"  Loaded {len(self.config)} rows")
        
        self.steel_intensities = self._load_steel_intensities()
        self.ammonia_intensities = self._load_ammonia_intensities()
        
        self.countries = [col for col in self.config.columns 
                         if col not in ['metric_1', 'metric_2', 'metric_3', 'metric_4', 
                                       'year', 'scenario', 'units']]
        print(f"  Countries: {self.countries}")
        
    def _load_steel_intensities(self) -> Optional[pd.DataFrame]:
        path = self.interim_dir / 'steel_intensity_projections.csv'
        if path.exists():
            df = pd.read_csv(path)
            print(f"  Loaded steel intensities: {len(df)} rows")
            return df
        print(f"  Warning: Steel intensity file not found")
        return None
            
    def _load_ammonia_intensities(self) -> Optional[pd.DataFrame]:
        path = self.interim_dir / 'ammonia_intensity_projections.csv'
        if path.exists():
            df = pd.read_csv(path)
            print(f"  Loaded ammonia intensities: {len(df)} rows")
            return df
        print(f"  Warning: Ammonia intensity file not found")
        return None
    
    def get_intensity(self, sector: str, route: str, country: str, 
                     scenario: str, year: int) -> float:
        year_str = str(year)
        
        # For steel, use projection file
        if sector == 'iron and steel' and self.steel_intensities is not None:
            route_text = f"Energy intensity of {route}"
            mask = ((self.steel_intensities['route'] == route_text) &
                    (self.steel_intensities['scenario'] == scenario) &
                    (self.steel_intensities['year'] == year_str))
            result = self.steel_intensities.loc[mask, country]
            if not result.empty:
                return result.iloc[0]
        
        # For ammonia, use projection file
        if sector == 'ammonia' and self.ammonia_intensities is not None:
            route_text = f"Energy intensity of {route}"
            mask = ((self.ammonia_intensities['route'] == route_text) &
                    (self.ammonia_intensities['scenario'] == scenario) &
                    (self.ammonia_intensities['year'] == year_str))
            result = self.ammonia_intensities.loc[mask, country]
            if not result.empty:
                return result.iloc[0]
        
        # For other sectors, use intensity_base from config
        # Try exact match first
        mask = ((self.config['metric_1'] == sector) &
                (self.config['metric_2'] == 'intensity_base') &
                (self.config['metric_3'] == route))
        
        if not mask.any():
            # Try "Energy intensity of {route}" pattern
            route_text = f"Energy intensity of {route}"
            mask = ((self.config['metric_1'] == sector) &
                    (self.config['metric_2'] == 'intensity_base') &
                    (self.config['metric_3'] == route_text))
        
        if not mask.any():
            return 0.0
            
        result = self.config.loc[mask, country]
        if result.empty:
            return 0.0
        return result.iloc[0]
    
    def _add_route_energy(self, sector_data: pd.DataFrame, route: str,
                         route_production: float, intensity: float,
                         country: str, scenario: str, year_str: str,
                         energy_by_carrier: Dict[str, float]) -> Dict[str, float]:
        """Calculate and add energy for a specific technology route"""
        fuel_mask = ((sector_data['metric_2'] == 'fuel_share') &
                    (sector_data['metric_3'] == route) &
                    (sector_data['scenario'] == scenario) &
                    (sector_data['year'] == year_str))
        
        fuel_shares = sector_data.loc[fuel_mask, ['metric_4', country]].copy()
        fuel_shares.columns = ['fuel', 'share']
        
        for _, fuel_row in fuel_shares.iterrows():
            fuel = fuel_row['fuel']
            fuel_share = fuel_row['share']
            
            if pd.isna(fuel_share) or fuel_share == 0:
                continue
            
            energy_mwh = route_production * intensity * fuel_share
            
            carrier = FUEL_MAPPING.get(fuel, fuel)
            if carrier in energy_by_carrier:
                energy_by_carrier[carrier] += energy_mwh
        
        return energy_by_carrier
    
    def _add_unspecified_energy(self, sector_data: pd.DataFrame, sector: str,
                               country: str, scenario: str, year_str: str,
                               energy_by_carrier: Dict[str, float]) -> Dict[str, float]:
        """Add unspecified energy"""
        unspec_mask = ((sector_data['metric_2'] == 'fuel_share') &
                      (sector_data['metric_3'].str.contains('Unspecified', case=False, na=False)) &
                      (sector_data['scenario'] == scenario) &
                      (sector_data['year'] == year_str))
        
        if not unspec_mask.any():
            return energy_by_carrier
        
        unspec_fuels = sector_data.loc[unspec_mask, ['metric_4', country]].copy()
        unspec_fuels.columns = ['fuel', 'value']
        
        activity_mask = ((sector_data['metric_2'] == 'activity_factor') &
                       (sector_data['scenario'] == scenario) &
                       (sector_data['year'] == year_str))
        
        activity_factor = 1.0
        if activity_mask.any():
            activity_factor = sector_data.loc[activity_mask, country].iloc[0]
            if pd.isna(activity_factor):
                activity_factor = 1.0
        
        for _, unspec_row in unspec_fuels.iterrows():
            fuel = unspec_row['fuel']
            value = unspec_row['value']
            
            if pd.isna(value) or value == 0:
                continue
            
            energy_mwh = value * activity_factor
            
            carrier = FUEL_MAPPING.get(fuel, fuel)
            if carrier in energy_by_carrier:
                energy_by_carrier[carrier] += energy_mwh
        
        return energy_by_carrier
    
    def calculate_steel_energy(self, years: List[int], scenarios: List[str]) -> pd.DataFrame:
        """
        Calculate steel sector energy with hierarchical Primary/Secondary structure.
        Returns both exogenous energy AND endogenous steel demand.
        """
        print("\nCalculating iron and steel sector...")
        sector = 'iron and steel'
        sector_data = self.config[self.config['metric_1'] == sector].copy()
        results = []
        
        for country in self.countries:
            for scenario in scenarios:
                for year in years:
                    year_str = str(year)
                    
                    # Get production
                    prod_mask = ((sector_data['metric_2'] == 'production') &
                                (sector_data['scenario'] == scenario) &
                                (sector_data['year'] == year_str))
                    
                    if not prod_mask.any():
                        continue
                    
                    production = sector_data.loc[prod_mask, country].iloc[0]
                    if pd.isna(production) or production == 0:
                        continue
                    
                    # Get Primary/Secondary shares
                    primary_mask = ((sector_data['metric_2'] == 'technology_route') &
                                   (sector_data['metric_3'] == 'Primary steel production') &
                                   (sector_data['scenario'] == scenario) &
                                   (sector_data['year'] == year_str))
                    
                    secondary_mask = ((sector_data['metric_2'] == 'technology_route') &
                                     (sector_data['metric_3'] == 'Secondary steel production') &
                                     (sector_data['scenario'] == scenario) &
                                     (sector_data['year'] == year_str))
                    
                    primary_share = sector_data.loc[primary_mask, country].iloc[0] if primary_mask.any() else 0
                    secondary_share = sector_data.loc[secondary_mask, country].iloc[0] if secondary_mask.any() else 0
                    
                    energy_by_carrier = {carrier: 0.0 for carrier in CARRIER_ORDER}
                    
                    # === PRIMARY STEEL (BF+BOF + DR+EAF) ===
                    if primary_share > 0:
                        primary_production = production * primary_share
                        
                        # Get BF+BOF and DR+EAF shares within primary
                        bf_bof_mask = ((sector_data['metric_2'] == 'technology_route') &
                                      (sector_data['metric_3'] == 'BF+BOF') &
                                      (sector_data['scenario'] == scenario) &
                                      (sector_data['year'] == year_str))
                        
                        dr_eaf_mask = ((sector_data['metric_2'] == 'technology_route') &
                                      (sector_data['metric_3'] == 'DR+EAF') &
                                      (sector_data['scenario'] == scenario) &
                                      (sector_data['year'] == year_str))
                        
                        bf_bof_share = sector_data.loc[bf_bof_mask, country].iloc[0] if bf_bof_mask.any() else 0
                        dr_eaf_share = sector_data.loc[dr_eaf_mask, country].iloc[0] if dr_eaf_mask.any() else 0
                        
                        # BF+BOF route
                        if bf_bof_share > 0:
                            route_production = primary_production * bf_bof_share
                            intensity = self.get_intensity(sector, 'BF+BOF', country, scenario, year)
                            if intensity > 0:
                                energy_by_carrier = self._add_route_energy(
                                    sector_data, 'BF+BOF', route_production, intensity,
                                    country, scenario, year_str, energy_by_carrier
                                )
                        
                        # DR+EAF route
                        if dr_eaf_share > 0:
                            route_production = primary_production * dr_eaf_share
                            intensity = self.get_intensity(sector, 'DR+EAF', country, scenario, year)
                            if intensity > 0:
                                energy_by_carrier = self._add_route_energy(
                                    sector_data, 'DR+EAF', route_production, intensity,
                                    country, scenario, year_str, energy_by_carrier
                                )
                    
                    # === SECONDARY STEEL (Scrap EAF) ===
                    if secondary_share > 0:
                        secondary_production = production * secondary_share
                        intensity = self.get_intensity(sector, 'Scrap EAF', country, scenario, year)
                        if intensity > 0:
                            energy_by_carrier = self._add_route_energy(
                                sector_data, 'Scrap EAF', secondary_production, intensity,
                                country, scenario, year_str, energy_by_carrier
                            )
                    
                    # === CASTING, ROLLING & FINISHING (all production) ===
                    casting_intensity = self.get_intensity(sector, 'Casting, rolling & finishing', country, scenario, year)
                    if casting_intensity > 0:
                        energy_by_carrier = self._add_route_energy(
                            sector_data, 'Casting, rolling & finishing', production, casting_intensity,
                            country, scenario, year_str, energy_by_carrier
                        )
                    
                    # === UNSPECIFIED ===
                    energy_by_carrier = self._add_unspecified_energy(
                        sector_data, sector, country, scenario, year_str, energy_by_carrier
                    )
                    
                    # Store exogenous energy results
                    for carrier, energy in energy_by_carrier.items():
                        if energy > 0:
                            results.append({
                                'country': country,
                                'scenario': scenario,
                                'year': year,
                                'carrier': carrier,
                                'energy_MWh': energy
                            })
                    
                    # === ENDOGENOUS STEEL DEMAND ===
                    # Only PRIMARY steel creates new steel demand (from iron ore)
                    # Secondary steel (scrap) is recycling existing steel → no endogenous demand
                    if primary_share > 0:
                        primary_production = production * primary_share
                        results.append({
                            'country': country,
                            'scenario': scenario,
                            'year': year,
                            'carrier': 'steel',
                            'energy_MWh': primary_production  # tonnes (only primary)
                        })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} records (incl. endogenous steel)")
        return df
    
    def calculate_ammonia_energy(self, years: List[int], scenarios: List[str]) -> pd.DataFrame:
        """
        Calculate ammonia energy.
        Returns exogenous production energy AND endogenous ammonia demand (production + imports).
        """
        print("\nCalculating ammonia sector...")
        
        # Production volumes are in 'chemical and petrochemical' sector
        production_data = self.config[self.config['metric_1'] == 'chemical and petrochemical'].copy()
        
        # Technology routes and intensities are in 'ammonia' sector
        tech_data = self.config[self.config['metric_1'] == 'ammonia'].copy()
        
        results = []
        
        for country in self.countries:
            for scenario in scenarios:
                for year in years:
                    year_str = str(year)
                    
                    # Get production volumes from chemical sector
                    prod_mask = ((production_data['metric_2'] == 'production') &
                                (production_data['metric_3'] == 'ammonia production per year') &
                                (production_data['scenario'] == scenario) &
                                (production_data['year'] == year_str))
                    
                    production = 0
                    if prod_mask.any():
                        production = production_data.loc[prod_mask, country].iloc[0]
                        if pd.isna(production):
                            production = 0
                    
                    # Get import volumes from chemical sector
                    import_mask = ((production_data['metric_2'] == 'production') &
                                  (production_data['metric_3'] == 'ammonia import volumes per year') &
                                  (production_data['scenario'] == scenario) &
                                  (production_data['year'] == year_str))
                    
                    imports = 0
                    if import_mask.any():
                        imports = production_data.loc[import_mask, country].iloc[0]
                        if pd.isna(imports):
                            imports = 0
                    
                    # Calculate exogenous energy (only if production > 0)
                    if production > 0:
                        energy_by_carrier = {carrier: 0.0 for carrier in CARRIER_ORDER}
                        
                        # Get technology routes from ammonia sector
                        route_mask = ((tech_data['metric_2'] == 'technology_route') &
                                     (tech_data['scenario'] == scenario) &
                                     (tech_data['year'] == year_str))
                        
                        routes = tech_data.loc[route_mask, ['metric_3', country]].copy()
                        routes.columns = ['route', 'share']
                        
                        for _, route_row in routes.iterrows():
                            route = route_row['route']
                            route_share = route_row['share']
                            
                            if pd.isna(route_share) or route_share == 0:
                                continue
                            
                            intensity = self.get_intensity('ammonia', route, country, scenario, year)
                            
                            if intensity > 0:
                                route_production = production * route_share
                                energy_by_carrier = self._add_route_energy(
                                    tech_data, route, route_production, intensity,
                                    country, scenario, year_str, energy_by_carrier
                                )
                        
                        # Add unspecified from tech_data
                        energy_by_carrier = self._add_unspecified_energy(
                            tech_data, 'ammonia', country, scenario, year_str, energy_by_carrier
                        )
                        
                        # Store exogenous energy
                        for carrier, energy in energy_by_carrier.items():
                            if energy > 0:
                                results.append({
                                    'country': country,
                                    'scenario': scenario,
                                    'year': year,
                                    'carrier': carrier,
                                    'energy_MWh': energy
                                })
                    
                    # === ENDOGENOUS AMMONIA DEMAND ===
                    total_ammonia_tonnes = production + imports
                    
                    if total_ammonia_tonnes > 0:
                        ammonia_energy_mwh = total_ammonia_tonnes * AMMONIA_LHV
                        
                        results.append({
                            'country': country,
                            'scenario': scenario,
                            'year': year,
                            'carrier': 'ammonia',
                            'energy_MWh': ammonia_energy_mwh
                        })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} records (incl. endogenous ammonia)")
        return df
    
    def calculate_hvc_energy(self, years: List[int], scenarios: List[str]) -> pd.DataFrame:
        """
        Calculate HVC (chemical and petrochemical) energy.
        Only exogenous energy (no endogenous carrier).
        """
        print("\nCalculating HVC sector...")
        sector = 'chemical and petrochemical'
        sector_data = self.config[self.config['metric_1'] == sector].copy()
        results = []
        
        for country in self.countries:
            for scenario in scenarios:
                for year in years:
                    year_str = str(year)
                    
                    # Get HVC production
                    prod_mask = ((sector_data['metric_2'] == 'production') &
                                (sector_data['metric_3'] == 'HVC production per year') &
                                (sector_data['scenario'] == scenario) &
                                (sector_data['year'] == year_str))
                    
                    if not prod_mask.any():
                        continue
                    
                    production = sector_data.loc[prod_mask, country].iloc[0]
                    if pd.isna(production) or production == 0:
                        continue
                    
                    energy_by_carrier = {carrier: 0.0 for carrier in CARRIER_ORDER}
                    
                    # Get technology routes
                    route_mask = ((sector_data['metric_2'] == 'technology_route') &
                                 (sector_data['scenario'] == scenario) &
                                 (sector_data['year'] == year_str))
                    
                    routes = sector_data.loc[route_mask, ['metric_3', country]].copy()
                    routes.columns = ['route', 'share']
                    
                    for _, route_row in routes.iterrows():
                        route = route_row['route']
                        route_share = route_row['share']
                        
                        if pd.isna(route_share) or route_share == 0:
                            continue
                        
                        intensity = self.get_intensity(sector, route, country, scenario, year)
                        
                        if intensity > 0:
                            route_production = production * route_share
                            energy_by_carrier = self._add_route_energy(
                                sector_data, route, route_production, intensity,
                                country, scenario, year_str, energy_by_carrier
                            )
                    
                    # Add unspecified
                    energy_by_carrier = self._add_unspecified_energy(
                        sector_data, sector, country, scenario, year_str, energy_by_carrier
                    )
                    
                    # Store results
                    for carrier, energy in energy_by_carrier.items():
                        if energy > 0:
                            results.append({
                                'country': country,
                                'scenario': scenario,
                                'year': year,
                                'carrier': carrier,
                                'energy_MWh': energy
                            })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} records")
        return df
    
    def calculate_generic_sector_energy(self, sector: str, years: List[int], scenarios: List[str]) -> pd.DataFrame:
        """Generic calculation for cement, paper, etc."""
        print(f"\nCalculating {sector} sector...")
        sector_data = self.config[self.config['metric_1'] == sector].copy()
        results = []
        
        # Route name mapping for simple sectors
        # technology_route metric_3 -> actual production route name
        ROUTE_NAME_MAPPING = {
            'Clinker ratio': 'Cement production',
            # Add more mappings if needed
        }
        
        for country in self.countries:
            for scenario in scenarios:
                for year in years:
                    year_str = str(year)
                    
                    prod_mask = ((sector_data['metric_2'] == 'production') &
                                (sector_data['scenario'] == scenario) &
                                (sector_data['year'] == year_str))
                    
                    if not prod_mask.any():
                        continue
                    
                    energy_by_carrier = {carrier: 0.0 for carrier in CARRIER_ORDER}
                    
                    # Special handling for paper & pulp (TWO productions: pulp and paper)
                    if sector == 'paper, pulp and printing':
                        # 1. Calculate PULP energy (with Primary/Secondary routes)
                        pulp_mask = prod_mask & (sector_data['metric_3'] == 'Pulp production per year')
                        if pulp_mask.any():
                            pulp_production = sector_data.loc[pulp_mask, country].iloc[0]
                            if not pd.isna(pulp_production) and pulp_production > 0:
                                route_mask = ((sector_data['metric_2'] == 'technology_route') &
                                            (sector_data['scenario'] == scenario) &
                                            (sector_data['year'] == year_str))
                                routes = sector_data.loc[route_mask, ['metric_3', country]].copy()
                                routes.columns = ['route', 'share']
                                
                                for _, route_row in routes.iterrows():
                                    route = route_row['route']
                                    route_share = route_row['share']
                                    if pd.isna(route_share) or route_share == 0:
                                        continue
                                    intensity = self.get_intensity(sector, route, country, scenario, year)
                                    if intensity > 0:
                                        route_production = pulp_production * route_share
                                        energy_by_carrier = self._add_route_energy(
                                            sector_data, route, route_production, intensity,
                                            country, scenario, year_str, energy_by_carrier
                                        )
                        
                        # 2. Calculate PAPER energy (no routes, direct intensity)
                        paper_mask = prod_mask & (sector_data['metric_3'] == 'Paper production per year')
                        if paper_mask.any():
                            paper_production = sector_data.loc[paper_mask, country].iloc[0]
                            if not pd.isna(paper_production) and paper_production > 0:
                                intensity = self.get_intensity(sector, 'Paper production', country, scenario, year)
                                if intensity > 0:
                                    energy_by_carrier = self._add_route_energy(
                                        sector_data, 'Paper production', paper_production, intensity,
                                        country, scenario, year_str, energy_by_carrier
                                    )
                    else:
                        # Standard logic for other sectors (single production with routes)
                        production = sector_data.loc[prod_mask, country].iloc[0]
                        if pd.isna(production) or production == 0:
                            continue
                        
                        route_mask = ((sector_data['metric_2'] == 'technology_route') &
                                     (sector_data['scenario'] == scenario) &
                                     (sector_data['year'] == year_str))
                        
                        routes = sector_data.loc[route_mask, ['metric_3', country]].copy()
                        routes.columns = ['route', 'share']
                        
                        for _, route_row in routes.iterrows():
                            route = route_row['route']
                            route_share = route_row['share']
                            
                            if pd.isna(route_share) or route_share == 0:
                                continue
                            
                            # Map route name for fuel share lookups
                            fuel_route_name = ROUTE_NAME_MAPPING.get(route, route)
                            
                            # Get intensity using the original route name
                            intensity = self.get_intensity(sector, fuel_route_name, country, scenario, year)
                            
                            if intensity > 0:
                                route_production = production * route_share
                                # Use mapped route name for fuel shares
                                energy_by_carrier = self._add_route_energy(
                                    sector_data, fuel_route_name, route_production, intensity,
                                    country, scenario, year_str, energy_by_carrier
                                )
                    
                    energy_by_carrier = self._add_unspecified_energy(
                        sector_data, sector, country, scenario, year_str, energy_by_carrier
                    )
                    
                    for carrier, energy in energy_by_carrier.items():
                        if energy > 0:
                            results.append({
                                'country': country,
                                'scenario': scenario,
                                'year': year,
                                'carrier': carrier,
                                'energy_MWh': energy
                            })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} records")
        return df
    
    def calculate_aluminium_energy(self, years: List[int], scenarios: List[str]) -> pd.DataFrame:
        """
        Calculate aluminium energy with Primary/Secondary route hierarchy.
        
        Similar to steel: production × route_share × intensity × fuel_share
        
        Routes:
        - Primary aluminium (Hall-Héroult): 64% (2020), energy-intensive
        - Secondary aluminium (Recycling): 36% (2020), low energy
        
        Returns:
            DataFrame with exogenous energy by carrier
        """
        print("\nCalculating aluminium (non-ferrous metals) sector...")
        sector = 'non-ferrous metals'
        sector_data = self.config[self.config['metric_1'] == sector].copy()
        results = []
        
        for country in self.countries:
            for scenario in scenarios:
                for year in years:
                    year_str = str(year)
                    
                    # Get total aluminium production
                    prod_mask = ((sector_data['metric_2'] == 'production') &
                                (sector_data['metric_3'] == 'Aluminium production per year') &
                                (sector_data['scenario'] == scenario) &
                                (sector_data['year'] == year_str))
                    
                    if not prod_mask.any():
                        continue
                    
                    production = sector_data.loc[prod_mask, country].iloc[0]
                    if pd.isna(production) or production == 0:
                        continue
                    
                    # Get Primary/Secondary shares
                    primary_mask = ((sector_data['metric_2'] == 'technology_route') &
                                   (sector_data['metric_3'] == 'Primary aluminium') &
                                   (sector_data['scenario'] == scenario) &
                                   (sector_data['year'] == year_str))
                    
                    secondary_mask = ((sector_data['metric_2'] == 'technology_route') &
                                     (sector_data['metric_3'] == 'Secondary aluminium') &
                                     (sector_data['scenario'] == scenario) &
                                     (sector_data['year'] == year_str))
                    
                    primary_share = sector_data.loc[primary_mask, country].iloc[0] if primary_mask.any() else 0
                    secondary_share = sector_data.loc[secondary_mask, country].iloc[0] if secondary_mask.any() else 0
                    
                    energy_by_carrier = {carrier: 0.0 for carrier in CARRIER_ORDER}
                    
                    # === PRIMARY ALUMINIUM (Hall-Héroult electrolysis) ===
                    if primary_share > 0:
                        primary_production = production * primary_share
                        intensity = self.get_intensity(sector, 'Primary aluminium', country, scenario, year)
                        if intensity > 0:
                            energy_by_carrier = self._add_route_energy(
                                sector_data, 'Primary aluminium', primary_production, intensity,
                                country, scenario, year_str, energy_by_carrier
                            )
                    
                    # === SECONDARY ALUMINIUM (Recycling) ===
                    if secondary_share > 0:
                        secondary_production = production * secondary_share
                        intensity = self.get_intensity(sector, 'Secondary aluminium', country, scenario, year)
                        if intensity > 0:
                            energy_by_carrier = self._add_route_energy(
                                sector_data, 'Secondary aluminium', secondary_production, intensity,
                                country, scenario, year_str, energy_by_carrier
                            )
                    
                    # === UNSPECIFIED (other non-ferrous: copper, zinc, lead, etc.) ===
                    # This is the RESIDUAL: UNSD total - aluminium detailed
                    energy_by_carrier = self._add_unspecified_energy(
                        sector_data, sector, country, scenario, year_str, energy_by_carrier
                    )
                    
                    # Store results
                    for carrier, energy in energy_by_carrier.items():
                        if energy > 0:
                            results.append({
                                'country': country,
                                'scenario': scenario,
                                'year': year,
                                'carrier': carrier,
                                'energy_MWh': energy
                            })
        
        df = pd.DataFrame(results)
        if not df.empty:
            print(f"  Generated {len(df)} records")
        return df
    
    def calculate_simple_sector_energy(self, sector_config_name: str, sector_output_name: str,
                                       years: List[int], scenarios: List[str]) -> pd.DataFrame:
        """
        Calculate energy demand for simple sectors (no production/intensity detail).
        
        METHODOLOGY - Separating Activity Growth and Efficiency Gains:
        ==============================================================
        
        Historical UNSD energy trends reflect: Total Energy = Activity × Efficiency
        
        For projections, we decompose into:
        1. ACTIVITY GROWTH: From UNSD historical CAGR (with IQR outlier capping)
        2. EFFICIENCY GAINS: Scenario-based storyline assumptions
        
        Formula:
        Energy(year, carrier) = BaseEnergy(2020) 
                               × (1 + activity_cagr)^years 
                               × (1 + efficiency_rate)^years
                               × FuelShare(carrier, year)
        
        Where:
        - activity_cagr = UNSD_CAGR × scenario_multiplier
        - efficiency_rate = scenario-dependent (negative for improvements)
        
        Scenario Parameters:
        - BAU: activity_mult=1.0×, efficiency=-1.0%/year
        - Progressive: activity_mult=1.2×, efficiency=-2.0%/year
        - Optimistic: activity_mult=1.5×, efficiency=-3.0%/year
        
        TODO: Review and adjust efficiency rates based on sector-specific studies.
        Current values are placeholder assumptions requiring validation against
        IEA/IRENA technology roadmaps for each sector.
        
        Args:
            sector_config_name: Name in INDUSTRY_CONFIG metric_1 (e.g., 'Food and tobacco')
            sector_output_name: Name for output column (e.g., 'food and tobacco')
            years: Target years
            scenarios: Scenarios
        
        Returns:
            DataFrame with columns: country, scenario, year, carrier, energy_MWh
        """
        from industry.core.helpers import get_historical_sector_data
        from industry.core.cagr_calculator import get_final_energy_cagr_from_unsd
        
        print(f"\nCalculating {sector_output_name} sector...")
        
        # Get fuel share rows from config
        fuel_shares = self.config[
            (self.config['metric_1'] == sector_config_name) &
            (self.config['metric_2'] == 'fuel_share')
        ].copy()
        
        if fuel_shares.empty:
            print(f"  Warning: No fuel shares found for {sector_config_name}")
            return pd.DataFrame()
        
        # UNSD data path
        industry_folder = Path(__file__).parent
        unsd_path = industry_folder / "input_data" / "unsdata_historical"
        
        # Scenario parameters - ACTIVITY GROWTH and EFFICIENCY GAINS
        scenario_params = {
            'BAU': {
                'activity_multiplier': 1.0,    # Historical activity trend continues
                'efficiency_rate': -0.010      # -1.0%/year efficiency improvement
            },
            'Progressive': {
                'activity_multiplier': 1.2,    # 20% faster activity growth
                'efficiency_rate': -0.020      # -2.0%/year efficiency improvement
            },
            'Optimistic': {
                'activity_multiplier': 1.5,    # 50% faster activity growth
                'efficiency_rate': -0.030      # -3.0%/year efficiency improvement
            }
        }
        
        results = []
        base_year = 2020
        
        for country in self.countries:
            # 1. Get base year total energy from UNSD (returns dict {year: GWh})
            historical_data = get_historical_sector_data(unsd_path, country, sector_config_name)
            
            if historical_data is None or base_year not in historical_data:
                # Try to get any available year
                if historical_data and len(historical_data) > 0:
                    available_years = sorted(historical_data.keys())
                    closest_year = min(available_years, key=lambda y: abs(y - base_year))
                    base_energy_gwh = historical_data[closest_year]
                    print(f"  {country}: Using {closest_year} data ({base_energy_gwh:,.0f} GWh) as base")
                else:
                    print(f"  {country}: No UNSD data, skipping")
                    continue
            else:
                base_energy_gwh = historical_data[base_year]
            
            # Convert GWh → MWh
            base_energy_mwh = base_energy_gwh * 1000
            
            # 2. Get ACTIVITY CAGR from UNSD historical trends (with IQR capping)
            # NOTE: This represents historical activity/volume growth (net of past efficiency)
            historical_cagr = get_final_energy_cagr_from_unsd(country, sector_config_name)
            
            # 3. Calculate for each scenario and year
            for scenario in scenarios:
                params = scenario_params.get(scenario, scenario_params['BAU'])
                
                # ACTIVITY growth = historical CAGR × scenario multiplier
                activity_cagr = historical_cagr * params['activity_multiplier']
                
                # EFFICIENCY improvement (negative rate = improvement)
                efficiency_rate = params['efficiency_rate']
                
                for year in years:
                    years_elapsed = year - base_year
                    
                    # Project total energy with SEPARATED activity and efficiency components
                    # Energy = Base × Activity_Growth × Efficiency_Change
                    activity_factor = (1 + activity_cagr) ** years_elapsed
                    efficiency_factor = (1 + efficiency_rate) ** years_elapsed
                    
                    projected_energy_mwh = base_energy_mwh * activity_factor * efficiency_factor
                    
                    # 4. Apply fuel shares (note: years in config are strings)
                    year_shares = fuel_shares[
                        (fuel_shares['year'] == str(year)) &
                        (fuel_shares['scenario'] == scenario)
                    ]
                    
                    if year_shares.empty:
                        continue
                    
                    # Get fuel shares for this country
                    for _, share_row in year_shares.iterrows():
                        fuel = share_row['metric_4']
                        share_value = share_row[country]
                        
                        if pd.notna(share_value) and share_value > 0:
                            # Map fuel name to carrier
                            carrier = FUEL_MAPPING.get(fuel, fuel)
                            
                            # Calculate energy for this fuel
                            fuel_energy = projected_energy_mwh * share_value
                            
                            if fuel_energy > 0:
                                results.append({
                                    'country': country,
                                    'scenario': scenario,
                                    'year': year,
                                    'carrier': carrier,
                                    'energy_MWh': fuel_energy
                                })
        
        df = pd.DataFrame(results)
        if not df.empty:
            # Aggregate by carrier (in case multiple fuels map to same carrier)
            df = df.groupby(['country', 'scenario', 'year', 'carrier'], as_index=False)['energy_MWh'].sum()
            print(f"  Generated {len(df)} records")
        else:
            print(f"  No data generated")
        
        return df
    
    def calculate_all_detailed_sectors(self, years: List[int] = [2030, 2035, 2040, 2045, 2050],
                                       scenarios: List[str] = ['BAU', 'Progressive', 'Optimistic']) -> pd.DataFrame:
        """Calculate all detailed sectors"""
        print("\n" + "="*80)
        print("CALCULATING FINAL ENERGY DEMAND FOR DETAILED SECTORS")
        print("="*80)
        
        all_results = []
        
        # Steel (with endogenous)
        steel_df = self.calculate_steel_energy(years, scenarios)
        if not steel_df.empty:
            steel_df['sector'] = 'iron and steel'
            all_results.append(steel_df)
        
        # Ammonia (with endogenous)
        ammonia_df = self.calculate_ammonia_energy(years, scenarios)
        if not ammonia_df.empty:
            ammonia_df['sector'] = 'chemical and petrochemical'
            all_results.append(ammonia_df)
        
        # HVC (exogenous only)
        hvc_df = self.calculate_hvc_energy(years, scenarios)
        if not hvc_df.empty:
            hvc_df['sector'] = 'chemical and petrochemical'
            all_results.append(hvc_df)
        
        # Cement
        cement_df = self.calculate_generic_sector_energy('non-metallic minerals', years, scenarios)
        if not cement_df.empty:
            cement_df['sector'] = 'non-metallic minerals'
            all_results.append(cement_df)
        
        # Paper & Pulp
        paper_df = self.calculate_generic_sector_energy('paper, pulp and printing', years, scenarios)
        if not paper_df.empty:
            paper_df['sector'] = 'paper pulp and print'
            all_results.append(paper_df)
        
        # Aluminium (non-ferrous metals)
        aluminium_df = self.calculate_aluminium_energy(years, scenarios)
        if not aluminium_df.empty:
            aluminium_df['sector'] = 'non-ferrous metals'
            all_results.append(aluminium_df)
        
        # ========== SIMPLE SECTORS (PyPSA-Earth approach) ==========
        # These use base year energy × CAGR projection × fuel shares
        
        simple_sectors = [
            ('Food and tobacco', 'food and tobacco'),
            ('Manufacturing  const. and mining', 'construction'),
            ('Machinery', 'machinery'),
            ('Mining and quarrying', 'mining and quarrying'),
            # NOTE: Non-ferrous metals removed - now handled as detailed sector (aluminium)
            ('Textile and leather', 'textile and leather'),
            ('Transport equipment', 'transport equipment'),
            ('Wood and wood products', 'wood and wood products'),
            ('Industry n.e.s', 'other industries')  # Catch-all for industries not elsewhere specified
        ]
        
        for config_name, output_name in simple_sectors:
            simple_df = self.calculate_simple_sector_energy(config_name, output_name, years, scenarios)
            if not simple_df.empty:
                simple_df['sector'] = output_name
                all_results.append(simple_df)
        
        if not all_results:
            print("\nWarning: No results generated!")
            return pd.DataFrame()
        
        # Combine all sectors
        combined = pd.concat(all_results, ignore_index=True)
        
        # Sum ammonia + HVC energies (share same output column)
        combined = combined.groupby(
            ['country', 'scenario', 'year', 'carrier', 'sector'], 
            as_index=False
        )['energy_MWh'].sum()
        
        print(f"\n" + "="*80)
        print(f"TOTAL: {len(combined)} energy demand records")
        print("="*80)
        
        return combined
    
    def pivot_to_wide_format(self, long_df: pd.DataFrame) -> pd.DataFrame:
        """Convert long format to wide format (sectors as columns)"""
        output_sectors = [
            'chemical and petrochemical',
            'iron and steel',
            'non-metallic minerals',
            'paper pulp and print',
            'machinery',
            'construction',
            'non-ferrous metals',
            'transport equipment',
            'food and tobacco',
            'mining and quarrying',
            'textile and leather',
            'wood and wood products',
            'other industries'
        ]
        
        wide = long_df.pivot_table(
            index=['country', 'scenario', 'year', 'carrier'],
            columns='sector',
            values='energy_MWh',
            aggfunc='sum',
            fill_value=0
        ).reset_index()
        
        # Ensure all sectors present
        for sector in output_sectors:
            if sector not in wide.columns:
                wide[sector] = 0
        
        # Reorder columns
        column_order = ['country', 'scenario', 'year', 'carrier'] + output_sectors
        wide = wide[column_order]
        
        # Sort
        wide = wide.sort_values(['country', 'year', 'scenario', 'carrier'])
        
        return wide
    
    def export_pypsa_format(self, wide_df: pd.DataFrame, output_dir: Path,
                           process_emissions_path: Path = None) -> List[Path]:
        """
        Export scenario-year CSV files in PyPSA format.
        
        - One CSV per scenario-year combination
        - Drop 'scenario' and 'year' columns
        - Add process emissions as a carrier row (same level as oil, gas, etc.)
        
        Args:
            wide_df: Wide format energy demand DataFrame
            output_dir: Output directory for PyPSA CSVs
            process_emissions_path: Path to process_emissions_summary.csv
        
        Returns:
            List of generated file paths
        """
        print("\n" + "="*80)
        print("EXPORTING PYPSA-FORMAT FILES (scenario-year CSVs + process emissions)")
        print("="*80)
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load process emissions if available
        process_emissions_df = None
        if process_emissions_path and process_emissions_path.exists():
            process_emissions_df = pd.read_csv(process_emissions_path)
            print(f"\nLoaded process emissions: {len(process_emissions_df)} rows")
        else:
            print(f"\nWarning: Process emissions not found at {process_emissions_path}")
            print("  Generating CSVs without process emissions")
        
        generated_files = []
        
        # Get unique scenario-year combinations
        scenario_years = wide_df[['scenario', 'year']].drop_duplicates().sort_values(['scenario', 'year'])
        
        for _, row in scenario_years.iterrows():
            scenario = row['scenario']
            year = int(row['year'])
            
            print(f"\nProcessing {scenario} {year}...")
            
            # Filter energy data for this scenario-year
            energy_data = wide_df[
                (wide_df['scenario'] == scenario) &
                (wide_df['year'] == year)
            ].copy()
            
            # Drop scenario and year columns
            energy_data = energy_data.drop(columns=['scenario', 'year'])
            
            # Add process emissions as a carrier row if available
            if process_emissions_df is not None:
                # Filter process emissions for this scenario-year
                pe_data = process_emissions_df[
                    (process_emissions_df['scenario'] == scenario) &
                    (process_emissions_df['year'] == year)
                ].copy()
                
                if not pe_data.empty:
                    # Pivot process emissions: sector columns with emissions values
                    pe_pivot = pe_data.pivot_table(
                        index='country',
                        columns='sector',
                        values='emissions_MtCO2',
                        aggfunc='sum',
                        fill_value=0
                    ).reset_index()
                    
                    # Add carrier column
                    pe_pivot['carrier'] = 'process_emissions'
                    
                    # Align columns with energy_data
                    # Get all sector columns from energy_data
                    sector_cols = [col for col in energy_data.columns if col not in ['country', 'carrier']]
                    
                    # Ensure process emissions has all sector columns
                    for col in sector_cols:
                        if col not in pe_pivot.columns:
                            pe_pivot[col] = 0
                    
                    # Reorder columns to match energy_data
                    pe_pivot = pe_pivot[['country', 'carrier'] + sector_cols]
                    
                    # Append process emissions row(s) to energy data
                    energy_data = pd.concat([energy_data, pe_pivot], ignore_index=True)
                    print(f"  Added process emissions: {len(pe_pivot)} rows")
            
            # Sort by country and carrier
            energy_data = energy_data.sort_values(['country', 'carrier'])
            
            # Generate filename: industry+{scenario}+{year}.csv
            scenario_slug = scenario.lower().replace(' ', '_')
            filename = f"industry+{scenario_slug}+{year}.csv"
            output_path = output_dir / filename
            
            # Save
            energy_data.to_csv(output_path, index=False)
            generated_files.append(output_path)
            print(f"  Saved: {filename} ({len(energy_data)} rows)")
        
        print("\n" + "="*80)
        print(f"GENERATED {len(generated_files)} PYPSA-FORMAT FILES")
        print("="*80)
        for path in generated_files:
            print(f"  - {path.name}")
        
        return generated_files


def main():
    """Main entry point"""
    base_dir = Path(__file__).parent
    config_path = base_dir / 'output_data' / 'CONFIG' / 'INDUSTRY_CONFIG.csv'
    interim_dir = base_dir / 'output_data' / 'interim_data'
    output_dir = base_dir / 'output_data'
    
    # Initialize
    calculator = FinalEnergyCalculator(config_path, interim_dir)
    
    # Calculate
    results_long = calculator.calculate_all_detailed_sectors(
        years=[2030, 2035, 2040, 2045, 2050],
        scenarios=['BAU', 'Progressive', 'Optimistic']
    )
    
    if results_long.empty:
        print("\nError: No results generated!")
        return
    
    # Save long format
    output_long_path = output_dir / 'final_energy_demand_detailed_sectors_long.csv'
    results_long.to_csv(output_long_path, index=False)
    print(f"\n[OK] Saved long format to: {output_long_path}")
    
    # Convert to wide format
    results_wide = calculator.pivot_to_wide_format(results_long)
    
    # Save wide format
    output_wide_path = output_dir / 'final_energy_demand_detailed_sectors_wide.csv'
    results_wide.to_csv(output_wide_path, index=False)
    print(f"[OK] Saved wide format to: {output_wide_path}")
    
    # Export PyPSA-format CSVs (scenario-year files with process emissions)
    process_emissions_path = output_dir / 'process_emissions_summary.csv'
    
    pypsa_files = calculator.export_pypsa_format(
        wide_df=results_wide,
        output_dir=output_dir,
        process_emissions_path=process_emissions_path
    )
    
    # Display sample
    print("\n" + "="*80)
    print("SAMPLE OUTPUT (Morocco, 2030, Optimistic):")
    print("="*80)
    sample = results_wide[
        (results_wide['country'] == 'Morocco') &
        (results_wide['year'] == 2030) &
        (results_wide['scenario'] == 'Optimistic')
    ]
    if not sample.empty:
        print(sample.to_string(index=False))
    
    print("\n[OK] Calculation complete!")


if __name__ == '__main__':
    main()
