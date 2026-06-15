"""
Calculate final energy demand from INDUSTRY_CONFIG.csv

Implements hierarchical steel calculation, endogenous demands for ammonia and steel,
and proper chemical sector aggregation (ammonia + HVC).
"""

import pandas as pd
import numpy as np
import argparse
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, cast
import warnings

warnings.filterwarnings('ignore')

# Define carrier order
CARRIER_ORDER = ['oil', 'gas', 'electricity', 'coal', 'heat', 'biomass', 
                 'hydrogen', 'ammonia', 'methanol', 'steel']

# Map INDUSTRY_CONFIG metric_1 names to UNSD sector names for data lookup
# CRITICAL: UNSD uses different names than our standardized config
CONFIG_TO_UNSD_SECTOR = {
    'other': 'Industry n.e.s',  # FIX: 'other' renamed from 'industry n.e.s' during standardization
    # Other sectors use same names in both config and UNSD, no mapping needed
}

# Map INDUSTRY_CONFIG metric_1 names to output column names
SECTOR_NAME_MAPPING = {
    'iron and steel': 'iron and steel',
    'chemical and petrochemical': 'chemical and petrochemical',  # Includes ammonia and HVC
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
    
    def __init__(
        self,
        config_path: Path,
        interim_dir: Path,
        output_suffix: str = '',
        refresh_interim: bool = True,
        refresh_years: Optional[List[int]] = None,
        refresh_scenarios: Optional[List[str]] = None,
    ):
        self.config_path = config_path
        self.interim_dir = interim_dir
        self.output_suffix = output_suffix
        
        print(f"Loading configuration from {config_path}...")
        self.config = pd.read_csv(config_path)
        print(f"  Loaded {len(self.config)} rows")

        self.countries = [col for col in self.config.columns 
                         if col not in ['metric_1', 'metric_2', 'metric_3', 'metric_4', 
                                       'year', 'scenario', 'units']]

        # Ensure all country value columns are numeric across loaded tables.
        # Some CSV exports can contain numeric-looking strings which break
        # comparisons like `share > 0` during sector calculations.
        self.config = self._coerce_country_columns_to_numeric(self.config)
        self._recalculate_production_from_cagr(base_year=2020)

        self.steel_intensities = None
        self.ammonia_intensities = None

        years = refresh_years if refresh_years is not None else [2030, 2035, 2040, 2045, 2050]
        scenarios = refresh_scenarios if refresh_scenarios is not None else ['BAU', 'Progressive', 'Optimistic']
        refresh_outputs = self._refresh_interim_projections(
            years=years,
            scenarios=scenarios,
            write_outputs=refresh_interim,
        )
        self.steel_intensities = refresh_outputs.get('steel_intensities')
        self.ammonia_intensities = refresh_outputs.get('ammonia_intensities')

        if self.steel_intensities is not None:
            self.steel_intensities = self._coerce_country_columns_to_numeric(self.steel_intensities)
        if self.ammonia_intensities is not None:
            self.ammonia_intensities = self._coerce_country_columns_to_numeric(self.ammonia_intensities)

        print(f"  Countries: {self.countries}")

    def _coerce_country_columns_to_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        """Coerce known country columns to numeric when present in a table."""
        out = df.copy()
        for country in self.countries:
            if country in out.columns:
                raw = out[country]
                text = raw.astype(str).str.strip()
                text = text.replace({'': pd.NA, '-': pd.NA, 'nan': pd.NA, 'None': pd.NA})
                is_percent = text.str.endswith('%', na=False)
                # Handle thousands separators and stray internal whitespace.
                normalized = text.str.replace(',', '', regex=False)
                normalized = normalized.str.replace(r'\s+', '', regex=True)
                numeric = pd.to_numeric(normalized.str.rstrip('%'), errors='coerce')
                numeric.loc[is_percent] = numeric.loc[is_percent] / 100.0
                out[country] = numeric
        return out

    def _interim_file_path(self, stem: str) -> Path:
        suffix = self.output_suffix or ''
        return self.interim_dir / f"{stem}{suffix}.csv"
    
    def _parse_period(self, value: str) -> Optional[tuple[int, int]]:
        text = str(value).strip()
        if '-' not in text:
            return None
        left, right = text.split('-', 1)
        if not left.isdigit() or not right.isdigit():
            return None
        start = int(left)
        end = int(right)
        if end <= start:
            return None
        return (start, end)

    def _build_period_rows(
        self,
        cfg: pd.DataFrame,
        metric_1_value: str,
        metric_3_value: str,
        scenario: str,
    ) -> List[tuple[int, int, pd.Series]]:
        mask = (
            (cfg['metric_1'].astype(str).str.lower() == metric_1_value)
            & (cfg['metric_2'].astype(str).str.lower() == 'cagr')
            & (cfg['metric_3'].astype(str).str.lower() == metric_3_value)
            & (cfg['scenario'] == scenario)
        )
        rows = cfg.loc[mask].copy()
        period_rows: List[tuple[int, int, pd.Series]] = []
        for _, row in rows.iterrows():
            period = self._parse_period(str(row['year']))
            if period is None:
                continue
            start, end = period
            period_rows.append((start, end, cast(pd.Series, row)))
        period_rows.sort(key=lambda item: (item[0], item[1]))
        return period_rows

    def _recalculate_one_production_series_from_cagr(
        self,
        cfg: pd.DataFrame,
        base_year: int,
        metric_1_value: str,
        production_metric_3: str,
        cagr_metric_3: str,
    ) -> int:
        prod_mask = (
            (cfg['metric_1'].astype(str).str.lower() == metric_1_value)
            & (cfg['metric_2'].astype(str).str.lower() == 'production')
            & (cfg['metric_3'].astype(str).str.lower() == production_metric_3)
        )
        if not prod_mask.any():
            return 0

        updates = 0
        scenarios = cfg.loc[prod_mask, 'scenario'].dropna().unique().tolist()
        year_numeric = pd.to_numeric(cfg['year'], errors='coerce')

        for scenario in scenarios:
            base_row_mask = prod_mask & (cfg['scenario'] == scenario) & (year_numeric == base_year)
            if not base_row_mask.any():
                continue

            period_rows = self._build_period_rows(cfg, metric_1_value, cagr_metric_3, scenario)
            if not period_rows:
                continue

            current_values: Dict[str, float] = {}
            for country in self.countries:
                values = cast(pd.Series, cfg.loc[base_row_mask, country])
                base_val = values.iloc[0] if not values.empty else 0.0
                current_values[country] = float(base_val) if pd.notna(base_val) else 0.0

            current_year = base_year
            for start, end, cagr_row in period_rows:
                if start != current_year:
                    continue

                years_delta = end - start
                target_row_mask = prod_mask & (cfg['scenario'] == scenario) & (year_numeric == end)

                for country in self.countries:
                    raw_cagr = cagr_row.get(country, 0.0)
                    cagr_value = float(raw_cagr) if pd.notna(raw_cagr) else 0.0
                    projected = current_values[country] * ((1.0 + cagr_value) ** years_delta)
                    current_values[country] = projected
                    if target_row_mask.any():
                        cfg.loc[target_row_mask, country] = projected
                        updates += 1

                current_year = end

        return updates

    def _recalculate_production_from_cagr(self, base_year: int = 2020) -> None:
        """Recompute configured production series from production CAGR rows in-place."""
        cfg = self.config
        specs = [
            ('iron and steel', 'steel production per year', 'steel production per year'),
            ('paper, pulp and printing', 'paper production per year', 'paper production per year'),
            ('paper, pulp and printing', 'pulp production per year', 'pulp production per year'),
            ('chemical and petrochemical', 'hvc production per year', 'hvc production per year'),
            ('chemical and petrochemical', 'ammonia production per year', 'ammonia production'),
            ('non-ferrous metals', 'aluminium production per year', 'aluminium production per year'),
            ('non-metallic minerals', 'cement production per year', 'cement production per year'),
        ]

        total_updates = 0
        for metric_1_value, production_metric_3, cagr_metric_3 in specs:
            total_updates += self._recalculate_one_production_series_from_cagr(
                cfg=cfg,
                base_year=base_year,
                metric_1_value=metric_1_value,
                production_metric_3=production_metric_3,
                cagr_metric_3=cagr_metric_3,
            )

        if total_updates > 0:
            print(f"  Recomputed production from CAGR rows ({total_updates} country-year updates)")

    def _normalize_config_for_interim_builders(self) -> pd.DataFrame:
        """Normalize config fields to the schema expected by interim projection builders."""
        df = self.config.copy()
        df['metric_1'] = df['metric_1'].astype(str).str.lower().replace({'industry n.e.s': 'other'})
        df['metric_2'] = df['metric_2'].astype(str).str.lower().replace({'energy_intensity': 'intensity_base'})
        df['metric_3'] = df['metric_3'].astype(str).str.lower()
        df['metric_4'] = df['metric_4'].fillna('').astype(str).str.lower()
        df['year'] = df['year'].apply(lambda x: int(str(x)) if str(x).isdigit() else str(x))
        return self._coerce_country_columns_to_numeric(df)

    def _refresh_interim_projections(self, years: List[int], scenarios: List[str], write_outputs: bool = True) -> Dict[str, Optional[pd.DataFrame]]:
        """Rebuild interim projection files from the currently selected config."""
        from industry.scripts.generate_industry_config import (
            build_steel_intensity_projections,
            build_ammonia_intensity_projections,
            build_steel_volumes,
        )
        from industry.scripts.chemical_and_petrochemical.ammonia.generate_ammonia_config import (
            build_ammonia_volumes_csv,
        )
        from industry.scripts.calculate_process_emissions import generate_process_emissions_reports
        from industry.utils.cagr_reporting import export_cagr_reports

        print("  Refreshing interim projections from selected config...")

        cfg = self._normalize_config_for_interim_builders()
        self.interim_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(
            dir=self.interim_dir.parent,
            prefix=f"refresh_{self.output_suffix.strip('_') or 'base'}_",
        ) as temp_dir_name:
            temp_dir = Path(temp_dir_name)

            steel_intensity_path = self._interim_file_path('steel_intensity_projections') if write_outputs else temp_dir / 'steel_intensity_projections.csv'
            ammonia_intensity_path = self._interim_file_path('ammonia_intensity_projections') if write_outputs else temp_dir / 'ammonia_intensity_projections.csv'
            steel_volumes_path = self._interim_file_path('steel_volumes') if write_outputs else temp_dir / 'steel_volumes.csv'
            ammonia_volumes_path = self._interim_file_path('ammonia_volumes') if write_outputs else temp_dir / 'ammonia_volumes.csv'
            production_cagr_path = self._interim_file_path('production_cagr') if write_outputs else temp_dir / 'production_cagr.csv'
            intensity_cagr_path = self._interim_file_path('intensity_cagr') if write_outputs else temp_dir / 'intensity_cagr.csv'
            intensity_cagr_summary_path = self._interim_file_path('intensity_cagr_summary') if write_outputs else temp_dir / 'intensity_cagr_summary.csv'
            process_emissions_path = self._interim_file_path('process_emissions') if write_outputs else temp_dir / 'process_emissions.csv'
            process_emissions_summary_path = self._interim_file_path('process_emissions_summary') if write_outputs else temp_dir / 'process_emissions_summary.csv'

            steel_intensity_df = build_steel_intensity_projections(
                cfg,
                self.countries,
                2020,
                years,
                scenarios,
                steel_intensity_path,
            )
            ammonia_intensity_df = build_ammonia_intensity_projections(
                cfg,
                self.countries,
                2020,
                years,
                scenarios,
                ammonia_intensity_path,
            )
            build_steel_volumes(
                cfg,
                self.countries,
                2020,
                years,
                scenarios,
                steel_volumes_path,
            )

            ammonia_vol_df = build_ammonia_volumes_csv(
                df_ammonia_config=cfg,
                countries=self.countries,
                base_year=2020,
                target_years=years,
                scenarios=scenarios,
                output_dir=temp_dir,
            )
            if write_outputs:
                shutil.copy2(temp_dir / 'ammonia_volumes.csv', ammonia_volumes_path)

            cagr_outputs = export_cagr_reports(
                df_config=cfg,
                output_dir=temp_dir,
                countries=self.countries,
                verbose=True,
            )
            if write_outputs:
                shutil.copy2(cagr_outputs['production'], production_cagr_path)
                shutil.copy2(cagr_outputs['intensity'], intensity_cagr_path)
                shutil.copy2(cagr_outputs['summary'], intensity_cagr_summary_path)

            emissions_outputs = generate_process_emissions_reports(
                df_config=cfg,
                output_dir=temp_dir,
                years=years,
                scenarios=scenarios,
            )
            if write_outputs:
                shutil.copy2(emissions_outputs['detailed'], process_emissions_path)
                shutil.copy2(emissions_outputs['summary'], process_emissions_summary_path)

        return {
            'steel_intensities': steel_intensity_df,
            'ammonia_intensities': ammonia_intensity_df,
            'ammonia_volumes': ammonia_vol_df,
        }

    def _project_value_from_period_cagr(
        self,
        period_rows: List[tuple[int, int, pd.Series]],
        country: str,
        target_year: int,
        base_year: int,
        base_value: float,
    ) -> float:
        if target_year <= base_year:
            return base_value

        period_map: Dict[int, tuple[int, pd.Series]] = {}
        for start, end, row in period_rows:
            if start not in period_map:
                period_map[start] = (end, row)

        current_year = base_year
        value = base_value

        while current_year < target_year:
            if current_year not in period_map:
                break

            end_year, row = period_map[current_year]
            step_end = min(end_year, target_year)
            raw_cagr = row.get(country, 0.0)
            cagr_value = float(raw_cagr) if pd.notna(raw_cagr) else 0.0
            value *= (1.0 + cagr_value) ** (step_end - current_year)
            current_year = step_end

            if step_end < end_year:
                break

        return value

    def _get_intensity_from_config(
        self,
        sector: str,
        route: str,
        country: str,
        scenario: str,
        year: int,
        base_year: int = 2020,
    ) -> Optional[float]:
        cfg = self.config
        metric_1 = cfg['metric_1'].astype(str).str.lower()
        metric_2 = cfg['metric_2'].astype(str).str.lower()
        metric_3 = cfg['metric_3'].astype(str).str.lower()

        sector_key = str(sector).lower()
        route_key = str(route).lower()
        route_candidates = [route_key]

        prefixed = f"energy intensity of {route_key}"
        if prefixed not in route_candidates:
            route_candidates.append(prefixed)
        if route_key.startswith('energy intensity of '):
            bare = route_key.replace('energy intensity of ', '', 1)
            if bare not in route_candidates:
                route_candidates.append(bare)

        base_mask = (
            (metric_1 == sector_key)
            & (metric_2 == 'intensity_base')
            & (metric_3.isin(route_candidates))
        )
        if not base_mask.any():
            return None

        base_rows = cfg.loc[base_mask].copy()
        scenario_rows = base_rows[base_rows['scenario'] == scenario]
        if not scenario_rows.empty:
            base_rows = scenario_rows

        base_rows['year_num'] = pd.to_numeric(base_rows['year'], errors='coerce')
        base_year_rows = base_rows[base_rows['year_num'] == base_year]
        selected = base_year_rows.iloc[0] if not base_year_rows.empty else base_rows.iloc[0]

        base_value_raw = selected.get(country, 0.0)
        base_value = float(base_value_raw) if pd.notna(base_value_raw) else 0.0

        units = str(selected.get('units', ''))
        if units == 'MWh/100t':
            base_value = base_value / 100.0

        cagr_mask = (
            (metric_1 == sector_key)
            & (metric_2 == 'cagr')
            & (metric_3.isin(route_candidates))
            & (cfg['scenario'] == scenario)
        )
        cagr_rows_df = cfg.loc[cagr_mask].copy()
        period_rows: List[tuple[int, int, pd.Series]] = []
        for _, row in cagr_rows_df.iterrows():
            period = self._parse_period(str(row['year']))
            if period is None:
                continue
            start, end = period
            period_rows.append((start, end, cast(pd.Series, row)))
        period_rows.sort(key=lambda item: (item[0], item[1]))

        return self._project_value_from_period_cagr(
            period_rows=period_rows,
            country=country,
            target_year=year,
            base_year=base_year,
            base_value=base_value,
        )
    
    def get_intensity(self, sector: str, route: str, country: str, 
                     scenario: str, year: int) -> float:
        projected = self._get_intensity_from_config(
            sector=sector,
            route=route,
            country=country,
            scenario=scenario,
            year=year,
            base_year=2020,
        )
        if projected is not None:
            return projected

        year_str = str(year)
        
        # For steel, use projection file
        if sector == 'iron and steel' and self.steel_intensities is not None:
            route_text = f"energy intensity of {route}"
            mask = ((self.steel_intensities['route'] == route_text) &
                    (self.steel_intensities['scenario'] == scenario) &
                    (self.steel_intensities['year'] == year_str))
            result = self.steel_intensities.loc[mask, country]
            if not result.empty:
                return result.iloc[0]
        
        # For ammonia, use projection file (now under chemical and petrochemical)
        if sector in ['ammonia', 'chemical and petrochemical'] and self.ammonia_intensities is not None:
            route_text = f"energy intensity of {route}"
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
            # Try "energy intensity of {route}" pattern (lowercase after standardization)
            route_text = f"energy intensity of {route}"
            mask = ((self.config['metric_1'] == sector) &
                    (self.config['metric_2'] == 'intensity_base') &
                    (self.config['metric_3'] == route_text))
        
        if not mask.any():
            return 0.0
            
        result = self.config.loc[mask, country]
        if result.empty:
            return 0.0
        
        intensity_value = result.iloc[0]
        
        # CRITICAL FIX: Convert MWh/100t to MWh/t
        # After unit standardization, production is in tonnes (t/a)
        # but some intensities are still in MWh/100t
        # Check units and convert if needed
        units_result = self.config.loc[mask, 'units']
        if not units_result.empty:
            units = units_result.iloc[0]
            if units == 'MWh/100t':
                # Convert from MWh/100t to MWh/t by dividing by 100
                intensity_value = intensity_value / 100
        
        return intensity_value
    
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
                    
                    # Get Primary/Secondary shares (lowercase after standardization)
                    primary_mask = ((sector_data['metric_2'] == 'technology_route') &
                                   (sector_data['metric_3'] == 'primary steel production') &
                                   (sector_data['scenario'] == scenario) &
                                   (sector_data['year'] == year_str))
                    
                    secondary_mask = ((sector_data['metric_2'] == 'technology_route') &
                                     (sector_data['metric_3'] == 'secondary steel production') &
                                     (sector_data['scenario'] == scenario) &
                                     (sector_data['year'] == year_str))
                    
                    primary_share = sector_data.loc[primary_mask, country].iloc[0] if primary_mask.any() else 0
                    secondary_share = sector_data.loc[secondary_mask, country].iloc[0] if secondary_mask.any() else 0
                    
                    energy_by_carrier = {carrier: 0.0 for carrier in CARRIER_ORDER}
                    
                    # === PRIMARY STEEL (BF+BOF + DR+EAF) ===
                    if primary_share > 0:
                        primary_production = production * primary_share
                        
                        # Get BF+BOF and DR+EAF shares within primary (lowercase after standardization)
                        bf_bof_mask = ((sector_data['metric_2'] == 'technology_route') &
                                      (sector_data['metric_3'] == 'bf+bof') &
                                      (sector_data['scenario'] == scenario) &
                                      (sector_data['year'] == year_str))
                        
                        dr_eaf_mask = ((sector_data['metric_2'] == 'technology_route') &
                                      (sector_data['metric_3'] == 'dr+eaf') &
                                      (sector_data['scenario'] == scenario) &
                                      (sector_data['year'] == year_str))
                        
                        bf_bof_share = sector_data.loc[bf_bof_mask, country].iloc[0] if bf_bof_mask.any() else 0
                        dr_eaf_share = sector_data.loc[dr_eaf_mask, country].iloc[0] if dr_eaf_mask.any() else 0
                        
                        # BF+BOF route (lowercase after standardization)
                        if bf_bof_share > 0:
                            route_production = primary_production * bf_bof_share
                            intensity = self.get_intensity(sector, 'bf+bof', country, scenario, year)
                            if intensity > 0:
                                energy_by_carrier = self._add_route_energy(
                                    sector_data, 'bf+bof', route_production, intensity,
                                    country, scenario, year_str, energy_by_carrier
                                )
                        
                        # DR+EAF route (lowercase after standardization)
                        if dr_eaf_share > 0:
                            route_production = primary_production * dr_eaf_share
                            intensity = self.get_intensity(sector, 'dr+eaf', country, scenario, year)
                            if intensity > 0:
                                energy_by_carrier = self._add_route_energy(
                                    sector_data, 'dr+eaf', route_production, intensity,
                                    country, scenario, year_str, energy_by_carrier
                                )
                    
                    # === SECONDARY STEEL (Scrap EAF) ===
                    if secondary_share > 0:
                        secondary_production = production * secondary_share
                        intensity = self.get_intensity(sector, 'scrap eaf', country, scenario, year)
                        if intensity > 0:
                            energy_by_carrier = self._add_route_energy(
                                sector_data, 'scrap eaf', secondary_production, intensity,
                                country, scenario, year_str, energy_by_carrier
                            )
                    
                    # === CASTING, ROLLING & FINISHING (all production) ===
                    casting_intensity = self.get_intensity(sector, 'casting, rolling & finishing', country, scenario, year)
                    if casting_intensity > 0:
                        energy_by_carrier = self._add_route_energy(
                            sector_data, 'casting, rolling & finishing', production, casting_intensity,
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
                    # Endogenous = DR+EAF (green primary) + secondary scrap EAF
                    # Exogenous  = BF+BOF (conventional) only
                    dr_eaf_production = (production * primary_share * dr_eaf_share
                                         if primary_share > 0 and dr_eaf_share > 0 else 0.0)
                    sec_production = production * secondary_share if secondary_share > 0 else 0.0
                    endog_steel = dr_eaf_production + sec_production
                    if endog_steel > 0:
                        results.append({
                            'country': country,
                            'scenario': scenario,
                            'year': year,
                            'carrier': 'steel',
                            'energy_MWh': endog_steel  # tonnes (DR+EAF primary + secondary scrap)
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
        
        # All ammonia data is now under 'chemical and petrochemical' sector
        # (consolidated from previous split between 'chemical and petrochemical' and 'ammonia')
        sector_data = self.config[self.config['metric_1'] == 'chemical and petrochemical'].copy()
        
        results = []
        
        for country in self.countries:
            for scenario in scenarios:
                for year in years:
                    year_str = str(year)
                    
                    # Get production volumes
                    prod_mask = ((sector_data['metric_2'] == 'production') &
                                (sector_data['metric_3'] == 'ammonia production per year') &
                                (sector_data['scenario'] == scenario) &
                                (sector_data['year'] == year_str))
                    
                    production = 0
                    if prod_mask.any():
                        production = sector_data.loc[prod_mask, country].iloc[0]
                        if pd.isna(production):
                            production = 0
                    
                    # Get import volumes
                    import_mask = ((sector_data['metric_2'] == 'production') &
                                  (sector_data['metric_3'] == 'ammonia import volumes per year') &
                                  (sector_data['scenario'] == scenario) &
                                  (sector_data['year'] == year_str))
                    
                    imports = 0
                    if import_mask.any():
                        imports = sector_data.loc[import_mask, country].iloc[0]
                        if pd.isna(imports):
                            imports = 0
                    
                    # Calculate exogenous energy (only if production > 0)
                    if production > 0:
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
                            
                            # Use 'chemical and petrochemical' for intensity lookup (consolidated sector)
                            intensity = self.get_intensity('chemical and petrochemical', route, country, scenario, year)
                            
                            if intensity > 0:
                                route_production = production * route_share
                                energy_by_carrier = self._add_route_energy(
                                    sector_data, route, route_production, intensity,
                                    country, scenario, year_str, energy_by_carrier
                                )
                        
                        # Add unspecified from sector_data
                        energy_by_carrier = self._add_unspecified_energy(
                            sector_data, 'chemical and petrochemical', country, scenario, year_str, energy_by_carrier
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
                    # Endogenous ammonia is computed from config values:
                    #   local green share + green-reallocated imports, then converted to MWh with LHV
                    renewable_mask = ((sector_data['metric_2'] == 'technology_route') &
                                      (sector_data['metric_3'] == 'renewable synthesis') &
                                      (sector_data['scenario'] == scenario) &
                                      (sector_data['year'] == year_str))
                    import_realloc_mask = ((sector_data['metric_2'] == 'technology_route') &
                                           (sector_data['metric_3'] == 'import reallocation') &
                                           (sector_data['scenario'] == scenario) &
                                           (sector_data['year'] == year_str))
                    import_reallocated_mask = ((sector_data['metric_2'] == 'production') &
                                               (sector_data['metric_3'] == 'ammonia import reallocated volume per year') &
                                               (sector_data['scenario'] == scenario) &
                                               (sector_data['year'] == year_str))

                    renewable_share = sector_data.loc[renewable_mask, country].iloc[0] if renewable_mask.any() else 0.0
                    import_realloc_share = sector_data.loc[import_realloc_mask, country].iloc[0] if import_realloc_mask.any() else 0.0
                    import_reallocated = sector_data.loc[import_reallocated_mask, country].iloc[0] if import_reallocated_mask.any() else imports * import_realloc_share

                    # Validate local production route shares: smr+hb + renewable synthesis == 1.0
                    smr_mask = ((sector_data['metric_2'] == 'technology_route') &
                                (sector_data['metric_3'] == 'smr+hb') &
                                (sector_data['scenario'] == scenario) &
                                (sector_data['year'] == year_str))
                    smr_share = sector_data.loc[smr_mask, country].iloc[0] if smr_mask.any() else 0.0
                    if abs((smr_share + renewable_share) - 1.0) > 0.01:
                        print(f"  WARNING: {country} {scenario} {year}: smr+hb ({smr_share:.3f}) + "
                              f"renewable synthesis ({renewable_share:.3f}) = {smr_share + renewable_share:.3f} "
                              f"(expected 1.0).")

                    endog_ammonia_tonnes = production * renewable_share + import_reallocated
                    ammonia_energy_mwh = endog_ammonia_tonnes * AMMONIA_LHV

                    if ammonia_energy_mwh > 0:
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
                    
                    # Get HVC production (lowercase after standardization)
                    prod_mask = ((sector_data['metric_2'] == 'production') &
                                (sector_data['metric_3'] == 'hvc production per year') &
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
                        pulp_mask = prod_mask & (sector_data['metric_3'] == 'pulp production per year')
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
                        paper_mask = prod_mask & (sector_data['metric_3'] == 'paper production per year')
                        if paper_mask.any():
                            paper_production = sector_data.loc[paper_mask, country].iloc[0]
                            if not pd.isna(paper_production) and paper_production > 0:
                                intensity = self.get_intensity(sector, 'paper production', country, scenario, year)
                                if intensity > 0:
                                    energy_by_carrier = self._add_route_energy(
                                        sector_data, 'paper production', paper_production, intensity,
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
                            
                            if pd.isna(route) or pd.isna(route_share) or route_share == 0:
                                continue
                            route_name = str(route)
                            if not route_name:
                                continue
                            
                            # Map route name for fuel share lookups
                            fuel_route_name = ROUTE_NAME_MAPPING.get(route_name, route_name)
                            
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
                    
                    # Get total aluminium production (lowercase after standardization)
                    prod_mask = ((sector_data['metric_2'] == 'production') &
                                (sector_data['metric_3'] == 'aluminium production per year') &
                                (sector_data['scenario'] == scenario) &
                                (sector_data['year'] == year_str))
                    
                    if not prod_mask.any():
                        continue
                    
                    production = sector_data.loc[prod_mask, country].iloc[0]
                    if pd.isna(production) or production == 0:
                        continue
                    
                    # Get Primary/Secondary shares (lowercase after standardization)
                    primary_mask = ((sector_data['metric_2'] == 'technology_route') &
                                   (sector_data['metric_3'] == 'primary aluminium') &
                                   (sector_data['scenario'] == scenario) &
                                   (sector_data['year'] == year_str))
                    
                    secondary_mask = ((sector_data['metric_2'] == 'technology_route') &
                                     (sector_data['metric_3'] == 'secondary aluminium') &
                                     (sector_data['scenario'] == scenario) &
                                     (sector_data['year'] == year_str))
                    
                    primary_share = sector_data.loc[primary_mask, country].iloc[0] if primary_mask.any() else 0
                    secondary_share = sector_data.loc[secondary_mask, country].iloc[0] if secondary_mask.any() else 0
                    
                    energy_by_carrier = {carrier: 0.0 for carrier in CARRIER_ORDER}
                    
                    # === PRIMARY ALUMINIUM (Hall-Héroult electrolysis) ===
                    if primary_share > 0:
                        primary_production = production * primary_share
                        intensity = self.get_intensity(sector, 'primary aluminium', country, scenario, year)
                        if intensity > 0:
                            energy_by_carrier = self._add_route_energy(
                                sector_data, 'primary aluminium', primary_production, intensity,
                                country, scenario, year_str, energy_by_carrier
                            )
                    
                    # === SECONDARY ALUMINIUM (Recycling) ===
                    if secondary_share > 0:
                        secondary_production = production * secondary_share
                        intensity = self.get_intensity(sector, 'secondary aluminium', country, scenario, year)
                        if intensity > 0:
                            energy_by_carrier = self._add_route_energy(
                                sector_data, 'secondary aluminium', secondary_production, intensity,
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
        1. ACTIVITY GROWTH: From config-stored CAGR values generated from UNSD
        2. EFFICIENCY GAINS: Scenario-based storyline assumptions
        
        Formula:
        Energy(year, carrier) = BaseEnergy(2020) 
                               × (1 + activity_cagr)^years 
                               × (1 + efficiency_rate)^years
                               × FuelShare(carrier, year)
        
        Where:
        - activity_cagr = config CAGR for the scenario
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
        from industry.utils.helpers import get_historical_sector_data
        
        print(f"\nCalculating {sector_output_name} sector...")
        
        # Get fuel share rows from config
        fuel_shares = self.config[
            (self.config['metric_1'] == sector_config_name) &
            (self.config['metric_2'] == 'fuel_share')
        ].copy()
        activity_cagr_rows = self.config[
            (self.config['metric_1'] == sector_config_name) &
            (self.config['metric_2'] == 'cagr') &
            (self.config['metric_3'] == 'activity growth rate') &
            (self.config['year'].astype(str) == '2020-2050')
        ].copy()
        
        if fuel_shares.empty:
            print(f"  Warning: No fuel shares found for {sector_config_name}")
            return pd.DataFrame()
        if activity_cagr_rows.empty:
            print(f"  Warning: No activity CAGR rows found for {sector_config_name}")
            return pd.DataFrame()
        
        # CENTRALIZED UNSD DATA PATH
        # Use shared data folder: sectoral-energy-demands/data/country_specific/
        industry_folder = Path(__file__).resolve().parents[1]  # industry/
        unsd_path = industry_folder.parent / "data" / "country_specific"
        
        # Scenario parameters - EFFICIENCY GAINS
        scenario_params = {
            'BAU': {
                'efficiency_rate': -0.010      # -1.0%/year efficiency improvement
            },
            'Progressive': {
                'efficiency_rate': -0.020      # -2.0%/year efficiency improvement
            },
            'Optimistic': {
                'efficiency_rate': -0.030      # -3.0%/year efficiency improvement
            }
        }
        
        results = []
        base_year = 2020
        
        for country in self.countries:
            # 1. Map config sector name to UNSD sector name (if needed)
            # CRITICAL: UNSD may use different names than our standardized config
            unsd_sector_name = CONFIG_TO_UNSD_SECTOR.get(sector_config_name, sector_config_name)
            
            # 2. Get base year total energy from UNSD (returns dict {year: GWh})
            historical_data = get_historical_sector_data(unsd_path, country, unsd_sector_name)
            
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
            
            # 3. Read ACTIVITY CAGR from config rows generated during config build
            # 4. Calculate for each scenario and year
            for scenario in scenarios:
                params = scenario_params.get(scenario, scenario_params['BAU'])
                scenario_cagr = activity_cagr_rows[
                    activity_cagr_rows['scenario'] == scenario
                ]
                if scenario_cagr.empty:
                    print(f"  Warning: Missing activity CAGR for {sector_config_name} / {scenario}")
                    continue
                activity_cagr = scenario_cagr.iloc[0].get(country)
                if pd.isna(activity_cagr):
                    print(f"  Warning: Missing activity CAGR for {sector_config_name} / {scenario} / {country}")
                    continue
                
                # EFFICIENCY improvement (negative rate = improvement)
                efficiency_rate = params['efficiency_rate']
                
                for year in years:
                    years_elapsed = year - base_year
                    
                    # Project total energy with SEPARATED activity and efficiency components
                    # Energy = Base × Activity_Growth × Efficiency_Change
                    activity_factor = (1 + activity_cagr) ** years_elapsed
                    efficiency_factor = (1 + efficiency_rate) ** years_elapsed
                    
                    projected_energy_mwh = base_energy_mwh * activity_factor * efficiency_factor
                    
                    # 5. Apply fuel shares (note: years in config are strings)
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
            df = cast(
                pd.DataFrame,
                df.groupby(['country', 'scenario', 'year', 'carrier'], as_index=False)['energy_MWh'].sum(),
            )
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
        # NOTE: Using lowercase names after config standardization
        
        simple_sectors = [
            ('food and tobacco', 'food and tobacco'),
            ('manufacturing  const. and mining', 'construction'),
            ('machinery', 'machinery'),
            ('mining and quarrying', 'mining and quarrying'),
            # NOTE: Non-ferrous metals removed - now handled as detailed sector (aluminium)
            ('textile and leather', 'textile and leather'),
            ('transport equipment', 'transport equipment'),
            ('wood and wood products', 'wood and wood products'),
            ('other', 'other')  # Renamed from 'Industry n.e.s' during standardization
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
            'other'
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


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Calculate final energy demand from an INDUSTRY_CONFIG-style CSV.'
    )
    parser.add_argument(
        '--config-file',
        type=str,
        default= "industry/output_data/CONFIG/INDUSTRY_CONFIG_v0.2.csv",
        help='Path to config CSV (default: industry/output_data/CONFIG/INDUSTRY_CONFIG.csv).',
    )
    parser.add_argument(
        '--interim-dir',
        type=str,
        default=None,
        help='Directory with projection files (default: industry/output_data/interim_data).',
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for final demand CSVs (default: industry/output_data).',
    )
    parser.add_argument(
        '--output-suffix',
        type=str,
        default='v0.2',
        help='Optional suffix appended to output filenames (e.g., _v2).',
    )
    parser.add_argument(
        '--no-refresh-interim',
        action='store_true',
        help='Do not rebuild interim projection files before calculating final demand.',
    )
    parser.add_argument(
        '--years',
        type=int,
        nargs='+',
        default=[2030, 2035, 2040, 2045, 2050],
        help='Projection years to calculate (default: 2030 2035 2040 2045 2050).',
    )
    parser.add_argument(
        '--scenarios',
        type=str,
        nargs='+',
        default=['BAU', 'Progressive', 'Optimistic'],
        help='Scenarios to calculate (default: BAU Progressive Optimistic).',
    )
    args = parser.parse_args()

    # Normalize suffix to either '' or '_<value>' for consistent file naming.
    suffix = args.output_suffix.strip()
    if suffix and not suffix.startswith('_'):
        suffix = f'_{suffix}'

    # Go up from scripts/ to industry/ root
    base_dir = Path(__file__).resolve().parents[1]

    config_path = Path(args.config_file) if args.config_file else (base_dir / 'output_data' / 'CONFIG' / 'INDUSTRY_CONFIG.csv')
    interim_dir = Path(args.interim_dir) if args.interim_dir else (base_dir / 'output_data' / 'interim_data')
    output_dir = Path(args.output_dir) if args.output_dir else (base_dir / 'output_data')
    output_dir.mkdir(parents=True, exist_ok=True)

    if not config_path.exists():
        raise FileNotFoundError(f'Config file not found: {config_path}')

    print(f"Using config file: {config_path}")
    print(f"Using interim dir: {interim_dir}")
    print(f"Using output dir: {output_dir}")
    print(f"Using suffix: {suffix if suffix else '(none)'}")
    
    # Initialize
    calculator = FinalEnergyCalculator(
        config_path,
        interim_dir,
        output_suffix=suffix,
        refresh_interim=not args.no_refresh_interim,
        refresh_years=None,
        refresh_scenarios=None,
    )
    
    # Calculate
    results_long = calculator.calculate_all_detailed_sectors(
        years=args.years,
        scenarios=args.scenarios
    )
    
    if results_long.empty:
        print("\nError: No results generated!")
        return
    
    # Save long format
    output_long_path = output_dir / f'final_energy_demand_detailed_sectors_long{suffix}.csv'
    try:
        results_long.to_csv(output_long_path, index=False)
        print(f"\n[OK] Saved long format to: {output_long_path}")
    except PermissionError:
        fallback_long = output_dir / f'final_energy_demand_detailed_sectors_long{suffix}.generated.csv'
        results_long.to_csv(fallback_long, index=False)
        print(f"\n[WARN] Could not overwrite locked file: {output_long_path}")
        print(f"[OK] Saved long format to fallback: {fallback_long}")
    
    # Convert to wide format
    results_wide = calculator.pivot_to_wide_format(results_long)
    
    # Save wide format
    output_wide_path = output_dir / f'final_energy_demand_detailed_sectors_wide{suffix}.csv'
    try:
        results_wide.to_csv(output_wide_path, index=False)
        print(f"[OK] Saved wide format to: {output_wide_path}")
    except PermissionError:
        fallback_wide = output_dir / f'final_energy_demand_detailed_sectors_wide{suffix}.generated.csv'
        results_wide.to_csv(fallback_wide, index=False)
        print(f"[WARN] Could not overwrite locked file: {output_wide_path}")
        print(f"[OK] Saved wide format to fallback: {fallback_wide}")
    print(f"\n[INFO] PyPSA output generation moved to build_pypsa_energy_demands.py")
    print(f"[INFO] Run that script to generate industry_totals+scenario+year.csv files")
    
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
