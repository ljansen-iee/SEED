import os
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path 

# iron and steel
from scripts.iron_and_steel.build_steel_production import load_and_process_both, share_steel
from scripts.iron_and_steel.build_shares_steel import share_fuel_bf_ohf, share_fuel_bf_bof, share_fuel_dr_eaf, share_fuel_scrap_eaf,share_fuel_casting_rolling, share_fuel_unspecified_steel, override_steel_routes_positional
from scripts.iron_and_steel.build_energy_intensities_steel import intensity_bf_ohf, intensity_bf_bof, intensity_dr_eaf, intensity_scrap_eaf, intensity_casting_rolling
from helpers import extract_capacity_shares, extract_all_fuels, _build_rate_anchors_indexed,  _forecast_from_history_and_sparse_cagr, _get_value_by_index,  _interp_at, get_mapped_config_name, poly_project, get_historical_sector_data, validate_fuel_shares, country_to_iso2, METRIC_ORDER
# PAPER & PULP
from scripts.paper_and_pulp.build_paper_and_pulp_production import process_paper_pulp_data
from scripts.paper_and_pulp.build_share_primary_pulp import share_fuel_primary_pulp, share_fuel_secondary_pulp, share_fuel_paper, share_primary_secondary_pulp, share_fuel_unspecified_paper_pulp, activity_factor_unspecified_paper_pulp
from scripts.paper_and_pulp.build_energy_intensities_paper_pulp import intensity_primary_pulp, intensity_secondary_pulp, intensity_paper_production
# CEMENT
from scripts.non_metallic_minerals.build_energy_intensities_cement import intensity_cement_production, activity_factor_unspecified_nmm, build_unspecified_nmm_intensity
from scripts.non_metallic_minerals.build_shares_cement import share_fuel_cement_production, share_fuel_unspecified_nmm
from scripts.non_metallic_minerals.build_cement_production import get_cement_and_clinker
# === Ammonia ===
from scripts.chemical_and_petrochemical.ammonia.build_ammonia import ammonia_production, build_hvc_production_series, extract_for_countries_from_loader
from scripts.chemical_and_petrochemical.ammonia.build_shares_ammonia import share_fuel_ammonia_smr_hb, share_fuel_ammonia_renewable, share_fuel_hvc_naphtha_cracking, share_fuel_hvc_lpg_cracking, share_fuel_hvc_methanol_route, share_fuel_unspecified_chemicals, share_HVC_production
from scripts.chemical_and_petrochemical.ammonia.build_intensities_ammonia import intensity_ammonia_smr_hb, intensity_ammonia_renewable, intensity_hvc_naphtha_cracking, intensity_hvc_lpg_cracking, intensity_hvc_methanol_route, activity_factor_unspecified_chemicals
# === HVC Production ===
from scripts.chemical_and_petrochemical.HVC.build_hvc_production import get_hvc_production
# === Food & Tobacco ===
from scripts.food_and_tobacco.build_shares_food_and_tobacco import get_unsd_fuel_shares
# CAGR CONFIG
from build_CAGR import load_industry_config, interpolate_or_extrapolate, get_metric_cagr_cfg_from_excel, expand_with_cagr_smooth

BASE_YEAR = 2020
TARGET_YEARS = [2030, 2050]
# Scenario names - Edit this list to change scenario names across all scripts
SCENARIOS = ["BAU", "Progressive", "Optimistic"]
INDUSTRY_CONFIG_FILE = "industry_config.csv"

# === Project imports ===
BASE_DIR = Path(__file__).resolve().parent
UNSD_PATH = BASE_DIR / "input_data" / "country_specific"

# === Module-level constants (from config.py) ===
INDUSTRY_CONFIG_PATH = BASE_DIR / INDUSTRY_CONFIG_FILE


def main():
    # ---- USER SETTINGS (defaults from module constants) ----
    base_year = BASE_YEAR
    target_years = TARGET_YEARS
    scenarios = SCENARIOS

    industry_cfg_path = INDUSTRY_CONFIG_PATH
  

    print("===============================")
    print("Industry configuration")
    print(f"Using CAGR config file: {industry_cfg_path}")
    print("===============================\n")

    # ---- Countries ----
    countries_to_process = ["Morocco"]
                          #"Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Nigeria",
                          #"Algeria","Argentina","Brazil","Chile","Colombia","Peru","Venezuela",
                          #"Morocco","Tunisia","Tanzania", "South Africa","Libya",
                          #G20 countries
                           #"Australia", "Canada", "China", "France", "Germany",  
                          #"India", "Indonesia", "Italy", "Japan", "Mexico","Russia", "Saudi Arabia", 
                           #"South Korea", "United Kingdom","United States of America"

    industry_cagr_excel = load_industry_config(
    excel_path=industry_cfg_path,
    countries=countries_to_process,
    scenarios=scenarios,)

    # ---- Load input data ----
    df_steel_capacity, df_steel_production = load_and_process_both()
    df_pulp_paper = process_paper_pulp_data() 
    # === Load BF + OHF ===
    fuel_shares_bf_ohf = extract_all_fuels(share_fuel_bf_ohf, target_years, scenarios)
    intensities_bf_ohf = extract_all_fuels(intensity_bf_ohf, target_years, scenarios)

    # === Load BF + BOF ===
    fuel_shares_bf_bof = extract_all_fuels(share_fuel_bf_bof, target_years, scenarios)
    intensities_bf_bof = extract_all_fuels(intensity_bf_bof, target_years, scenarios)

    # === Load DR + EAF ===
    fuel_shares_dr_eaf = extract_all_fuels(share_fuel_dr_eaf, target_years, scenarios)
    intensities_dr_eaf = extract_all_fuels(intensity_dr_eaf, target_years, scenarios)

    # === Load Scrap EAF ===
    fuel_shares_scrap_eaf = extract_all_fuels(share_fuel_scrap_eaf, target_years, scenarios)
    intensities_scrap_eaf = extract_all_fuels(intensity_scrap_eaf, target_years, scenarios)

    # === Load Casting, Rolling & Finishing ===
    fuel_shares_casting_rolling = extract_all_fuels(share_fuel_casting_rolling, target_years, scenarios)
    intensities_casting_rolling = intensity_casting_rolling(target_years, scenarios) 

    # === Load Unspecified Steel ===
    fuel_shares_unspecified = extract_all_fuels(share_fuel_unspecified_steel, target_years, scenarios)

    # === Pulp & Paper fuel shares ===
    fuel_shares_primary_pulp   = extract_all_fuels(share_fuel_primary_pulp,   target_years, scenarios)
    fuel_shares_secondary_pulp = extract_all_fuels(share_fuel_secondary_pulp, target_years, scenarios)
    fuel_shares_paper          = extract_all_fuels(share_fuel_paper,          target_years, scenarios)
    fuel_shares_unspec_pp      = extract_all_fuels(share_fuel_unspecified_paper_pulp, target_years, scenarios)

    # === Pulp & Paper intensities ===
    intensities_primary_pulp   = extract_all_fuels(intensity_primary_pulp,   target_years, scenarios)
    intensities_secondary_pulp = extract_all_fuels(intensity_secondary_pulp, target_years, scenarios)
    intensities_paper          = extract_all_fuels(intensity_paper_production, target_years, scenarios)

    # === Pulp primary vs secondary share (not fuel-specific; category split) ===
    pp_primary_secondary_share = share_primary_secondary_pulp(target_years, scenarios)  # dict: category -> year -> scenario


    # === Cement fuel shares & intensities ===
    cement_fuel_shares = share_fuel_cement_production(target_years, scenarios)
    cement_intensities = intensity_cement_production(target_years, scenarios)
    
    # === Unspecified Non-metallic minerals (NMM) fuel shares ===
    unspec_nmm_fuel_shares = share_fuel_unspecified_nmm(target_years, scenarios)

    # === Ammonia fuel shares ===
    fuel_shares_ammonia_smrhb   = extract_all_fuels(share_fuel_ammonia_smr_hb, target_years, scenarios)
    fuel_shares_ammonia_renew   = extract_all_fuels(share_fuel_ammonia_renewable, target_years, scenarios)
    df_ammonia = ammonia_production() 
    # Ammonia intensities (by route)
    intens_ammonia_smrhb   = extract_all_fuels(intensity_ammonia_smr_hb,       target_years, scenarios)
    intens_ammonia_renew   = extract_all_fuels(intensity_ammonia_renewable,    target_years, scenarios)

    # HVC shares & intensities (if you want them now)
    # === HVC production from industrial database ===
    df_hvc_production = get_hvc_production(add_country_names=False)

    fuel_shares_hvc_naphtha = extract_all_fuels(share_fuel_hvc_naphtha_cracking, target_years, scenarios)
    fuel_shares_hvc_lpg     = extract_all_fuels(share_fuel_hvc_lpg_cracking,     target_years, scenarios)
    fuel_shares_hvc_meth    = extract_all_fuels(share_fuel_hvc_methanol_route,   target_years, scenarios)


    intens_hvc_naphtha = extract_all_fuels(intensity_hvc_naphtha_cracking, target_years, scenarios)
    intens_hvc_lpg     = extract_all_fuels(intensity_hvc_lpg_cracking,     target_years, scenarios)
    intens_hvc_meth    = extract_all_fuels(intensity_hvc_methanol_route,   target_years, scenarios)
    
    hvc_route_shares = share_HVC_production(target_years, scenarios)
    
    share_fuel_unspecified = extract_all_fuels(share_fuel_unspecified_chemicals, target_years, scenarios)
    # Create output path using country_parameters subfolder (aligned with transport)
    output_root = BASE_DIR / "output_data" / "country_parameters"
    output_root.mkdir(parents=True, exist_ok=True)

    
    for country in countries_to_process:

        cagr_cfg_nmm = get_metric_cagr_cfg_from_excel( industry_cagr_excel,country,"Activity factor of unspecified non metallic minerals")
        nmm_activity = activity_factor_unspecified_nmm(
            base_value=1.00,
            base_year=base_year,
            target_years=target_years,
            cagr_cfg=cagr_cfg_nmm,
            scenarios=scenarios,
            use_profile=False  # set True if you want to use the fixed level profile
        )
        # === HVC production source (real industrial database) ===
        hvc_prod_source = {}
        iso = country_to_iso2(country)
        row_hvc = df_hvc_production[df_hvc_production["country"] == iso]

        if not row_hvc.empty:
            base_val = float(row_hvc["HVC_production_t_per_year"].iloc[0])
        else:
            base_val = 0.0

        if base_val == 0.0:
            print(f" No HVC data for {country} ({iso}) — using 0")

        hvc_prod_source[base_year] = [base_val] * len(scenarios)

        # === Project using CAGR (same logic as other sectors) ===
        hvc_cagr_cfg = get_metric_cagr_cfg_from_excel(
            industry_cagr_excel,
            country,
            "High value chemical production per year"
        )

        hvc_proj = expand_with_cagr_smooth(
            base_value=base_val,
            cagr_table=hvc_cagr_cfg,
            base_year=base_year,
            target_years=target_years,
            scenarios=scenarios
        )
        
        for key, val in hvc_proj.items():
            year, scenario = key.split("_")
            year = int(year)
            if year not in hvc_prod_source:
                hvc_prod_source[year] = [None] * len(scenarios)
            idx = scenarios.index(scenario)
            hvc_prod_source[year][idx] = val

        cagr_cfg_unspec_pp = get_metric_cagr_cfg_from_excel(
        industry_cagr_excel,
        country,
        "Activity factor of unspecified paper and pulp")

        act_unspec_pp = activity_factor_unspecified_paper_pulp(
            base_year=base_year,
            target_years=target_years,
            scenarios=scenarios,
            cagr_cfg=cagr_cfg_unspec_pp,  # <- drives interpolation/extrapolation
            base_value=1.0,
            use_profile=False,
        )
        unspec_chem_cagr = get_metric_cagr_cfg_from_excel( industry_cagr_excel, country,"Activity factor of unspecified chemicals")
        act_unspec_chem = activity_factor_unspecified_chemicals(
            base_year=base_year,
            target_years=target_years,
            scenarios=scenarios,
            cagr_cfg=unspec_chem_cagr,
            base_value=1.0,
        )
        # === Load static shares ===
        share_primary_steel, share_secondary_steel = share_steel(target_years, scenarios)
        # === Define all steel types in your dataset ===
        all_steel_types = ["Blast oxygen furnace", "Open hearth furnace", "Electric arc furnace"]

        # === Compute flexible shares (mutually exclusive) ===
        share_bf_ohf = extract_capacity_shares(
            df=df_steel_capacity,
            country=country,
            steel_types=["Open hearth furnace"],     
            base_year=base_year,
            target_years=target_years,
            all_types=all_steel_types
        )

        share_bf_bof = extract_capacity_shares(
            df=df_steel_capacity,
            country=country,
            steel_types=["Blast oxygen furnace"],    # BF (BF+BOF route)
            base_year=base_year,
            target_years=target_years,
            all_types=all_steel_types
        )

        share_dr_eaf = extract_capacity_shares(
            df=df_steel_capacity,
            country=country,
            steel_types=["Electric arc furnace"],  
            base_year=base_year,
            target_years=target_years,
            all_types=all_steel_types
        )
        share_bf_ohf, share_bf_bof, share_dr_eaf, has_override = override_steel_routes_positional(
            country=country,
            target_years=target_years,
            scenarios=scenarios,
            share_bf_ohf=share_bf_ohf,
            share_bf_bof=share_bf_bof,
            share_dr_eaf=share_dr_eaf,
            base_year=base_year,
        )
      
        # --- SECTOR DATA & GROWTH LOGIC ---
        unsd_sectors = [
            ("wood and wood products", "Wood and wood products", "final energy of wood and wood products"),
            ("transport equipment", "Transport equipment", "final energy of transport equipment"),
            ("textile and leather", "Textile and leather", "final energy of textile and leather"),
            ("mining and quarrying", "Mining and quarrying", "final energy of mining and quarrying"),
            ("machinery", "Machinery", "final energy of machinery"),
            ("construction", "Construction", "final energy of construction"),
            ("food and tobacco", "Food and tobacco", "final energy of food and tobacco"),
            ("non-ferrous metals", "Non-ferrous metals", "final energy of non-ferrous metals")
        ]

        results = {}
        all_fuels = ['electricity', 'oil', 'gas', 'coal', 'biomass', 'hydrogen', 'ammonia', 'steel','methanol', 'heat', 'low-temperature heat', "process emissions"]

        for s_id, csv_name, metric_name in unsd_sectors:
            # A. Get Total Energy (GWh) from CSV
            hist_total = get_historical_sector_data(UNSD_PATH, country, csv_name)
            if isinstance(hist_total, dict):
                base_total_val = float(hist_total.get(base_year, 0.0))
            else:
                base_total_val = float(hist_total if hist_total else 0.0)

            # B. Get CAGR values (Already lowered in build_CAGR.py)
            cagr_values = get_metric_cagr_cfg_from_excel(industry_cagr_excel, country, metric_name.lower())
            
            # C. Create Scenario-Aware Time Series for Total Energy
            total_time_series = {}
            # Start with Base Year (Same value for all scenarios)
            total_time_series[base_year] = [base_total_val] * len(scenarios)
            
            # Project for 2030, 2050, etc.
            for y in target_years:
                vals_for_year = []
                for idx, sc in enumerate(scenarios):
                    # Extract the rate for this specific scenario index
                    # cagr_values looks like: { 2030: {"Baseline": 0.03, "AP": 0.0, ...} }
                    sc_name = scenarios[idx]
                    
                    # Construct a dummy anchor for the forecast function to handle one scenario at a time
                    # It expects: { Year: [Value] }
                    temp_anchors = {yr: [v_dict.get(sc_name, 0.0)] for yr, v_dict in cagr_values.items()}
                    
                    proj = _forecast_from_history_and_sparse_cagr(base_total_val, base_year, [y], temp_anchors, [sc_name])
                    
                    # Result key looks like "2030_Baseline"
                    val = proj.get(f"{y}_{sc_name}", base_total_val)
                    vals_for_year.append(float(val))
                
                total_time_series[y] = vals_for_year

            # D. Process Fuel Shares
            base_shares = get_unsd_fuel_shares(UNSD_PATH, country, base_year, sector_name=csv_name)
            fuel_shares_proj = {}
            
            for fuel in all_fuels:
                lookup_name = f"share of {fuel} for unspecified {s_id}".lower()
                
                # We need to see if the specific COUNTRY has a value
                # Check your build_CAGR.py to ensure this returns a dict of years/scenarios
                excel_share_values = get_metric_cagr_cfg_from_excel(industry_cagr_excel, country, lookup_name)
                
                fuel_series = {}
                for y in [base_year] + target_years:
                    vals = []
                    for idx, sc in enumerate(scenarios):
                        sc_name = scenarios[idx]
                        excel_val = excel_share_values.get(y, {}).get(sc_name)
                        
                        if excel_val is not None and not pd.isna(excel_val) and excel_val != 0.0:
                            # Use the specific instruction from Excel
                            vals.append(float(excel_val))
                        elif y == base_year:
                            # Always use history for the base year column
                            vals.append(float(base_shares.get(fuel, 0.0)))
                        else:
                            # For 2030/2050, if Excel is 0 or Blank, REPLICATE 2020
                            vals.append(float(base_shares.get(fuel, 0.0)))

                    fuel_series[y] = vals
                fuel_shares_proj[fuel] = fuel_series

            # Save results
            results[s_id] = {"total": total_time_series, "shares": fuel_shares_proj}
        
        # === Define metrics dictionary follows here ===
        # --- Get cement base value (t/y), clinker ratio path, clinker production path
        cement_tpy_2020, clinker_ratio, clinker_prod = get_cement_and_clinker(
            country_name=country,
            base_year=base_year,
            target_years=target_years,
            scenarios=scenarios,   
        )
        nmm_energy_cagr_cfg = get_metric_cagr_cfg_from_excel(
        industry_cagr_excel,
        country,
        "Energy intensity of unspecified non metallic minerals")
        nmm_energy_use = build_unspecified_nmm_intensity(
            cement_base_tpy=cement_tpy_2020 * 0.17,                        
            cement_diesel_intensity=cement_intensities["diesel"],   
            base_year=base_year,
            target_years=target_years,
            scenarios=scenarios,
            cagr_cfg=nmm_energy_cagr_cfg,
        )
                # --- Build ammonia per-country, per-scenario dict sources ---
        try:
            df_ammonia_extracted = extract_for_countries_from_loader(
                path=None,
                countries=[country],
                base_year=base_year,
                target_years=target_years,
                scenarios=scenarios,
            )
        except Exception as e:
            print(f" Warning: ammonia extraction failed for {country}: {e}")
            df_ammonia_extracted = None

        ammonia_prod_source = {}
        ammonia_share_smr_source = {}
        ammonia_share_renew_source = {}

        if df_ammonia_extracted is None or df_ammonia_extracted.empty:
            # leave empty dicts; downstream code handles missing data
            ammonia_prod_source = {}
            ammonia_share_smr_source = {}
            ammonia_share_renew_source = {}
        else:
            # helper: get per-scenario values for a year and vtype
            def _values_for_year_and_type(y: int, vtype: str):
                vals = []
                for sc in scenarios:
                    row = df_ammonia_extracted[
                        (df_ammonia_extracted.get("scenario_label", "") == sc) &
                        (df_ammonia_extracted.get("year") == y) &
                        (df_ammonia_extracted.get("value_type") == vtype)
                    ]
                    if not row.empty:
                        v = row["value"].iloc[0]
                        vals.append(float(v) if pd.notna(v) else None)
                    else:
                        vals.append(None)
                return vals

            # New rule: if the country has ANY non-zero local_production anywhere in extracted DF,
            # then for the base year prefer total_production (nearest available); otherwise use local_production.
            has_local_nonzero = False
            try:
                lp_rows = df_ammonia_extracted[df_ammonia_extracted["value_type"] == "local_production"]
                if not lp_rows.empty:
                    # if any non-zero numeric value present
                    has_local_nonzero = lp_rows["value"].apply(lambda x: pd.notna(x) and float(x) != 0.0).any()
            except Exception:
                has_local_nonzero = False

            # build base-year list according to rule
            base_vals = None
            if has_local_nonzero:
                # prefer total_production for base year
                base_vals = _values_for_year_and_type(base_year, "total_production")
                if all(v is None for v in base_vals):
                    base_vals = _values_for_year_and_type(base_year - 1, "total_production")
            else:
                # prefer local_production (nearest previous year)
                base_vals = _values_for_year_and_type(base_year, "local_production")
                if all(v is None for v in base_vals):
                    base_vals = _values_for_year_and_type(base_year - 1, "local_production")

            # fallback: if still all None, try aggregated df_ammonia (same value for all scenarios)
            if all(v is None for v in base_vals):
                try:
                    ag = df_ammonia.copy()
                    sub = ag[ag["country"].astype(str).str.strip() == str(country).strip()]
                    if not sub.empty:
                        # if we preferred total_production, look there, else look at local_production
                        if has_local_nonzero:
                            # pick nearest year <= base_year for total_production
                            le = sub[sub["year"] <= base_year]
                            if not le.empty:
                                v = float(le.sort_values("year").iloc[-1]["total_production"])
                            else:
                                v = float(sub.sort_values("year").iloc[0]["total_production"])
                        else:
                            le = sub[sub["year"] <= base_year]
                            if not le.empty:
                                v = float(le.sort_values("year").iloc[-1]["local_production"])
                            else:
                                v = float(sub.sort_values("year").iloc[0]["local_production"])
                        base_vals = [v] * len(scenarios)
                except Exception:
                    pass

            if any(v is not None for v in base_vals):
                ammonia_prod_source[base_year] = base_vals

            # TARGET years: total_production per scenario (with aggregated fallback/interpolation if missing)
            for y in target_years:
                vals = _values_for_year_and_type(y, "total_production")
                if all(v is None for v in vals):
                    # fallback: try aggregated df_ammonia interpolation
                    try:
                        ag = df_ammonia.copy()
                        sub = ag[ag["country"].astype(str).str.strip() == str(country).strip()]
                        if not sub.empty:
                            years = sub["year"].astype(int).to_numpy()
                            vals_col = sub["total_production"].astype(float).to_numpy()
                            if len(years) >= 1:
                                import numpy as _np
                                interp_v = float(_np.interp(y, years, vals_col))
                                vals = [interp_v] * len(scenarios)
                    except Exception:
                        pass
                ammonia_prod_source[y] = vals

            # shares: build for base and target years (try multiple possible value_type names)
            for y in [base_year] + list(target_years):
                vals_smr = _values_for_year_and_type(y, "share_smrhb")
                vals_renew = _values_for_year_and_type(y, "share_renew")

                # alternative header names if extractor used them
                if all(v is None for v in vals_smr):
                    vals_smr = _values_for_year_and_type(y, "Share of SMR + Haber-Bosch (%)")
                if all(v is None for v in vals_renew):
                    vals_renew = _values_for_year_and_type(y, "Share of renewable ammonia synthesis (%)")

                # fallback to aggregated df_ammonia if still missing
                if all(v is None for v in vals_smr):
                    try:
                        ag = df_ammonia.copy()
                        sub = ag[ag["country"].astype(str).str.strip() == str(country).strip()]
                        if not sub.empty:
                            le = sub[sub["year"] <= y]
                            if not le.empty:
                                v = float(le.sort_values("year").iloc[-1]["share_smrhb"])
                            else:
                                v = float(sub.sort_values("year").iloc[0]["share_smrhb"])
                            vals_smr = [v] * len(scenarios)
                    except Exception:
                        vals_smr = [None] * len(scenarios)

                if all(v is None for v in vals_renew):
                    try:
                        ag = df_ammonia.copy()
                        sub = ag[ag["country"].astype(str).str.strip() == str(country).strip()]
                        if not sub.empty:
                            le = sub[sub["year"] <= y]
                            if not le.empty:
                                v = float(le.sort_values("year").iloc[-1]["share_renew"])
                            else:
                                v = float(sub.sort_values("year").iloc[0]["share_renew"])
                            vals_renew = [v] * len(scenarios)
                    except Exception:
                        vals_renew = [None] * len(scenarios)

                ammonia_share_smr_source[y] = vals_smr
                ammonia_share_renew_source[y] = vals_renew


        # === Define metrics ===
        metrics: Dict[str, Dict[str, Any]] = {
            "Steel production per year": {
                "source": df_steel_production,
                "column": str(base_year),
                "unit": "tons/y",
                "forecast": True,
            },
            "Share of primary steel": {
                "source": share_primary_steel,
                "unit": "% of steel production",
                "forecast": False,
            },
            "Share of secondary steel = scrap electric arc furnaces": {
                "source": share_secondary_steel,
                "unit": "% of steel production",
                "forecast": False,
            },
            "Share of blast furnace + open hearth furnace for steel making": {
                "source": share_bf_ohf,
                "unit": "% of primary steel production",
                "forecast": not has_override,
            },
            "Share of blast furnace + basic oxygen furnace for steel making": {
                "source": share_bf_bof,
                "unit": "% of primary steel production",
                "forecast": not has_override,
            },
            "Share of direct reduction + electric arc furnace for steel making": {
                "source": share_dr_eaf,
                "unit": "% of primary steel production",
                "forecast": not has_override,
            },

            # === BF + OHF (fuel shares)
            "Share of diesel for blast furnaces": {
                "source": fuel_shares_bf_ohf["diesel"],
                "unit": "% of BF + OHF",
                "forecast": False,
            },
            "Share of natural gas for blast furnaces": {
                "source": fuel_shares_bf_ohf["natural_gas"],
                "unit": "% of BF + OHF",
                "forecast": False,
            },
            "Share of electricity for blast furnaces + open hearth furnace": {
                "source": fuel_shares_bf_ohf["electricity"],
                "unit": "% of BF + OHF",
                "forecast": False,
            },
            "Share of coal for blast furnaces + open hearth furnace": {
                "source": fuel_shares_bf_ohf["coal"],
                "unit": "% of BF + OHF",
                "forecast": False,
            },
            "Share of heat for blast furnaces + open hearth furnace": {
                "source": fuel_shares_bf_ohf["heat"],
                "unit": "% of BF + OHF",
                "forecast": False,
            },
            "Share of biomass for blast furnaces + open hearth furnace": {
                "source": fuel_shares_bf_ohf["biomass"],
                "unit": "% of BF + OHF",
                "forecast": False,
            },
            "Share of hydrogen for blast furnaces + open hearth furnace": {
                "source": fuel_shares_bf_ohf["hydrogen"],
                "unit": "% of BF + OHF",
                "forecast": False,
            },

            # === BF + OHF (intensities)
            "Energy intensity of diesel in blast furnaces + open hearth furnace": {
                "source": intensities_bf_ohf["diesel"],
                "unit": "MWh/t",
                "forecast": True,
            },
            "Energy intensity of natural gas in blast furnaces + open hearth furnace": {
                "source": intensities_bf_ohf["natural_gas"],
                "unit": "MWh/t",
                "forecast": True,
            },
            "Energy intensity of electricity in blast furnaces + open hearth furnace": {
                "source": intensities_bf_ohf["electricity"],
                "unit": "MWh/t",
                "forecast": True,
            },
            "Energy intensity of coal in blast furnaces + open hearth furnace": {
                "source": intensities_bf_ohf["coal"],
                "unit": "MWh/t",
                "forecast": True,
            },
            "Energy intensity of heat in blast furnaces + open hearth furnace": {
                "source": intensities_bf_ohf["heat"],
                "unit": "MWh/t",
                "forecast": True,
            },
            "Energy intensity of biomass in blast furnaces + open hearth furnace": {
                "source": intensities_bf_ohf["biomass"],
                "unit": "MWh/t",
                "forecast": True,
            },
            "Energy intensity of hydrogen in blast furnaces + open hearth furnace": {
                "source": intensities_bf_ohf["hydrogen"],
                "unit": "MWh/t",
                "forecast": True,
            },

             # === BF + BOF (fuel shares)
            "Share of diesel for blast furnaces + basic oxygen furnace": {
                "source": fuel_shares_bf_bof["diesel"],
                "unit": "% of BF + BOF",
                "forecast": False,
            },
            "Share of natural gas for blast furnaces + basic oxygen furnace": {
                "source": fuel_shares_bf_bof["natural_gas"],
                "unit": "% of BF + BOF",
                "forecast": False,
            },
            "Share of electricity for blast furnaces + basic oxygen furnace": {
                "source": fuel_shares_bf_bof["electricity"],
                "unit": "% of BF + BOF",
                "forecast": False,
            },
            "Share of coal for blast furnaces + basic oxygen furnace": {
                "source": fuel_shares_bf_bof["coal"],
                "unit": "% of BF + BOF",
                "forecast": False,
            },
            "Share of heat for blast furnaces + basic oxygen furnace": {
                "source": fuel_shares_bf_bof["heat"],
                "unit": "% of BF + BOF",
                "forecast": False,
            },
            "Share of biomass for blast furnaces + basic oxygen furnace": {
                "source": fuel_shares_bf_bof["biomass"],
                "unit": "% of BF + BOF",
                "forecast": False,
            },
            "Share of hydrogen for blast furnaces + basic oxygen furnace": {
                "source": fuel_shares_bf_bof["hydrogen"],
                "unit": "% of BF + BOF",
                "forecast": False,
            },

            # === BF + BOF (intensities)
            "Energy intensity of diesel in blast furnaces + basic oxygen furnace": {
                "source": intensities_bf_bof["diesel"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of natural gas in blast furnaces + basic oxygen furnace": {
                "source": intensities_bf_bof["natural_gas"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of electricity in blast furnaces + basic oxygen furnace": {
                "source": intensities_bf_bof["electricity"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of coal in blast furnaces + basic oxygen furnace": {
                "source": intensities_bf_bof["coal"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of heat in blast furnaces + basic oxygen furnace": {
                "source": intensities_bf_bof["heat"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of biomass in blast furnaces + basic oxygen furnace": {
                "source": intensities_bf_bof["biomass"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of hydrogen in blast furnaces + basic oxygen furnace": {
                "source": intensities_bf_bof["hydrogen"],
                "unit": "MWh/t",
                "forecast": False,
            },
            # === DR + EAF (fuel shares)
            "Share of diesel for direct reduction + electric arc furnace": {
                "source": fuel_shares_dr_eaf["diesel"],
                "unit": "% of DR + EAF",
                "forecast": False,
            },
            "Share of natural gas for direct reduction + electric arc furnace": {
                "source": fuel_shares_dr_eaf["natural_gas"],
                "unit": "% of DR + EAF",
                "forecast": False,
            },
            "Share of electricity for direct reduction + electric arc furnace": {
                "source": fuel_shares_dr_eaf["electricity"],
                "unit": "% of DR + EAF",
                "forecast": False,
            },
            "Share of coal for direct reduction + electric arc furnace": {
                "source": fuel_shares_dr_eaf["coal"],
                "unit": "% of DR + EAF",
                "forecast": False,
            },
            "Share of heat for direct reduction + electric arc furnace": {
                "source": fuel_shares_dr_eaf["heat"],
                "unit": "% of DR + EAF",
                "forecast": False,
            },
            "Share of biomass for direct reduction + electric arc furnace": {
                "source": fuel_shares_dr_eaf["biomass"],
                "unit": "% of DR + EAF",
                "forecast": False,
            },
            "Share of hydrogen for direct reduction + electric arc furnace": {
                "source": fuel_shares_dr_eaf["hydrogen"],
                "unit": "% of DR + EAF",
                "forecast": False,
            },

            # === DR + EAF (energy intensities)
            "Energy intensity of diesel in direct reduction + electric arc furnace": {
                "source": intensities_dr_eaf["diesel"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of natural gas in direct reduction + electric arc furnace": {
                "source": intensities_dr_eaf["natural_gas"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of electricity in direct reduction + electric arc furnace": {
                "source": intensities_dr_eaf["electricity"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of coal in direct reduction + electric arc furnace": {
                "source": intensities_dr_eaf["coal"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of heat in direct reduction + electric arc furnace": {
                "source": intensities_dr_eaf["heat"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of biomass in direct reduction + electric arc furnace": {
                "source": intensities_dr_eaf["biomass"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of hydrogen in direct reduction + electric arc furnace": {
                "source": intensities_dr_eaf["hydrogen"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Share of diesel for scrap electric arc furnaces": {
                "source": fuel_shares_scrap_eaf["diesel"],
                "unit": "% of scrap EAF",
                "forecast": False,
            },
            "Share of natural gas for scrap electric arc furnaces": {
                "source": fuel_shares_scrap_eaf["natural_gas"],
                "unit": "% of scrap EAF",
                "forecast": False,
            },
            "Share of electricity for scrap electric arc furnaces": {
                "source": fuel_shares_scrap_eaf["electricity"],
                "unit": "% of scrap EAF",
                "forecast": False,
            },
            "Share of coal for scrap electric arc furnaces": {
                "source": fuel_shares_scrap_eaf["coal"],
                "unit": "% of scrap EAF",
                "forecast": False,
            },
            "Share of heat for scrap electric arc furnaces": {
                "source": fuel_shares_scrap_eaf["heat"],
                "unit": "% of scrap EAF",
                "forecast": False,
            },
            "Share of biomass for scrap electric arc furnaces": {
                "source": fuel_shares_scrap_eaf["biomass"],
                "unit": "% of scrap EAF",
                "forecast": False,
            },
            "Share of hydrogen for scrap electric arc furnaces": {
                "source": fuel_shares_scrap_eaf["hydrogen"],
                "unit": "% of scrap EAF",
                "forecast": False,
            },
            "Energy intensity of diesel in scrap electric arc furnaces": {
                "source": intensities_scrap_eaf["diesel"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of natural gas in scrap electric arc furnaces": {
                "source": intensities_scrap_eaf["natural_gas"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of electricity in scrap electric arc furnaces": {
                "source": intensities_scrap_eaf["electricity"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of coal in scrap electric arc furnaces": {
                "source": intensities_scrap_eaf["coal"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of heat in scrap electric arc furnaces": {
                "source": intensities_scrap_eaf["heat"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of biomass in scrap electric arc furnaces": {
                "source": intensities_scrap_eaf["biomass"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of hydrogen in scrap electric arc furnaces": {
                "source": intensities_scrap_eaf["hydrogen"],
                "unit": "MWh/t",
                "forecast": False,
            },
            # === Casting, Rolling & Finishing ===
            "Share of diesel for casting, rolling & finishing": {
                "source": fuel_shares_casting_rolling["diesel"],
                "unit": "% of casting, rolling & finishing",
                "forecast": False,
            },
            "Share of natural gas for casting, rolling & finishing": {
                "source": fuel_shares_casting_rolling["natural_gas"],
                "unit": "% of casting, rolling & finishing",
                "forecast": False,
            },
            "Share of electricity for casting, rolling & finishing": {
                "source": fuel_shares_casting_rolling["electricity"],
                "unit": "% of casting, rolling & finishing",
                "forecast": False,
            },
            "Share of coal for casting, rolling & finishing": {
                "source": fuel_shares_casting_rolling["coal"],
                "unit": "% of casting, rolling & finishing",
                "forecast": False,
            },
            "Share of heat for casting, rolling & finishing": {
                "source": fuel_shares_casting_rolling["heat"],
                "unit": "% of casting, rolling & finishing",
                "forecast": False,
            },
            "Share of biomass for casting, rolling & finishing": {
                "source": fuel_shares_casting_rolling["biomass"],
                "unit": "% of casting, rolling & finishing",
                "forecast": False,
            },
            "Share of hydrogen for casting, rolling & finishing": {
                "source": fuel_shares_casting_rolling["hydrogen"],
                "unit": "% of casting, rolling & finishing",
                "forecast": False,
            },
            "Energy intensity of casting, rolling & finishing": {
                "source": intensities_casting_rolling[ "total"],
                "unit": "MWh/t",
                "forecast": False,
            },
            # === Unspecified Iron and Steel ===
            "Activity factor of unspecified iron and steel": {
                "source": df_steel_production,
                "column": str(base_year),
                "unit": "tons/y",
                "forecast": True,
            },
            "Share of diesel for unspecified iron and steel": {
                "source": fuel_shares_unspecified["diesel"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of natural gas for unspecified iron and steel": {
                "source": fuel_shares_unspecified["natural_gas"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of electricity for unspecified iron and steel": {
                "source": fuel_shares_unspecified["electricity"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of coal for unspecified iron and steel": {
                "source": fuel_shares_unspecified["coal"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of heat for unspecified iron and steel": {
                "source": fuel_shares_unspecified["heat"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of biomass for unspecified iron and steel": {
                "source": fuel_shares_unspecified["biomass"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of hydrogen for unspecified iron and steel": {
                "source": fuel_shares_unspecified["hydrogen"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Pulp production per year": {
                "source": df_pulp_paper,           
                "column": "Pulp_Production_tons",  
                "unit": "tons/y",
                "forecast": True,
            },

            "Share of primary pulp": {
                "source": pp_primary_secondary_share["primary"],  
                "unit": "% of pulp production",
                "forecast": False,
            },
            "Share of secondary pulp": {
                "source": pp_primary_secondary_share["secondary"],
                "unit": "% of pulp production",
                "forecast": False,
            },

            # --- Primary Pulp: fuel shares ---
            "Share of diesel for primary pulp production":      {
                "source": fuel_shares_primary_pulp["diesel"],      
                "unit": "% of primary pulp production", 
                "forecast": False},
            "Share of natural gas for primary pulp production": {
                "source": fuel_shares_primary_pulp["natural_gas"], 
                "unit": "% of primary pulp production", 
                "forecast": False},
            "Share of electricity for primary pulp production": {
                "source": fuel_shares_primary_pulp["electricity"], 
                "unit": "% of primary pulp production", 
                "forecast": False},
            "Share of coal for primary pulp production":        {
                "source": fuel_shares_primary_pulp["coal"],        
                "unit": "% of primary pulp production", 
                "forecast": False},
            "Share of heat for primary pulp production":        {
                "source": fuel_shares_primary_pulp["heat"],        
                "unit": "% of primary pulp production", 
                "forecast": False},
            "Share of biomass for primary pulp production":     {
                "source": fuel_shares_primary_pulp["biomass"],     
                "unit": "% of primary pulp production", 
                "forecast": False},
            "Share of hydrogen for primary pulp production":    {
                "source": fuel_shares_primary_pulp["hydrogen"],    
                "unit": "% of primary pulp production", 
                "forecast": False},

            "Energy intensity of diesel in primary pulp production":      {
                "source": intensities_primary_pulp["diesel"],      
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of natural gas in primary pulp production": {
                "source": intensities_primary_pulp["natural_gas"], 
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of electricity in primary pulp production": {
                "source": intensities_primary_pulp["electricity"], 
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of coal in primary pulp production":        {
                "source": intensities_primary_pulp["coal"],        
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of heat in primary pulp production":        {
                "source": intensities_primary_pulp["heat"],        
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of biomass in primary pulp production":     {
                "source": intensities_primary_pulp["biomass"],     
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of hydrogen in primary pulp production":    {
                "source": intensities_primary_pulp["hydrogen"],    
                "unit": "MWh/t", 
                "forecast": False},


            # --- Secondary Pulp: fuel shares ---
            "Share of diesel for secondary pulp production":      {
                "source": fuel_shares_secondary_pulp["diesel"],      
                "unit": "% of secondary pulp production", 
                "forecast": False},
            "Share of natural gas for secondary pulp production": {
                "source": fuel_shares_secondary_pulp["natural_gas"], 
                "unit": "% of secondary pulp production", 
                "forecast": False},
            "Share of electricity for secondary pulp production": {
                "source": fuel_shares_secondary_pulp["electricity"], 
                "unit": "% of secondary pulp production", 
                "forecast": False},
            "Share of coal for secondary pulp production":        {
                "source": fuel_shares_secondary_pulp["coal"],       
                "unit": "% of secondary pulp production", 
                "forecast": False},
            "Share of heat for secondary pulp production":        {
                "source": fuel_shares_secondary_pulp["heat"],        
                "unit": "% of secondary pulp production", 
                "forecast": False},
            "Share of biomass for secondary pulp production":     {
                "source": fuel_shares_secondary_pulp["biomass"],     
                "unit": "% of secondary pulp production", 
                "forecast": False},
            "Share of hydrogen for secondary pulp production":    {
                "source": fuel_shares_secondary_pulp["hydrogen"],   
                "unit": "% of secondary pulp production", 
                "forecast": False},

             "Energy intensity of diesel in secondary pulp production":      {
                "source": intensities_secondary_pulp["diesel"],      
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of natural gas in secondary pulp production": {
                "source": intensities_secondary_pulp["natural_gas"], 
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of electricity in secondary pulp production": {
                "source": intensities_secondary_pulp["electricity"], 
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of coal in secondary pulp production":        {
                "source": intensities_secondary_pulp["coal"],        
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of heat in secondary pulp production":        {
                "source": intensities_secondary_pulp["heat"],        
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of biomass in secondary pulp production":     {
                "source": intensities_secondary_pulp["biomass"],     
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of hydrogen in secondary pulp production":    {
                "source": intensities_secondary_pulp["hydrogen"],    
                "unit": "MWh/t", 
                "forecast": False
            },
            
             "Paper production per year": {
                "source": df_pulp_paper,
                "column": "Paper_Production_tons",
                "unit": "tons/y",
                "forecast": True,
            },
            # --- Paper: fuel shares ---
            "Share of diesel for paper production":      {
                "source": fuel_shares_paper["diesel"],      
                "unit": "% of paper production", 
                "forecast": False},
            "Share of natural gas for paper production": {
                "source": fuel_shares_paper["natural_gas"], 
                "unit": "% of paper production", 
                "forecast": False},
            "Share of electricity for paper production": {
                "source": fuel_shares_paper["electricity"], 
                "unit": "% of paper production", 
                "forecast": False},
            "Share of coal for paper production":        {
                "source": fuel_shares_paper["coal"],        
                "unit": "% of paper production", 
                "forecast": False},
            "Share of heat for paper production":        {
                "source": fuel_shares_paper["heat"],        
                "unit": "% of paper production", 
                "forecast": False},
            "Share of biomass for paper production":     {
                "source": fuel_shares_paper["biomass"],    
                "unit": "% of paper production", 
                "forecast": False},
            "Share of hydrogen for paper production":    {
                "source": fuel_shares_paper["hydrogen"],    
                "unit": "% of paper production", 
                "forecast": False},

            "Energy intensity of diesel in paper production": {
                "source": intensities_paper["diesel"],      
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of natural gas in paper production": {
                "source": intensities_paper["natural_gas"], 
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of electricity in paper production": {
                "source": intensities_paper["electricity"], 
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of coal in paper production":        {
                "source": intensities_paper["coal"],        
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of heat in paper production":        {
                "source": intensities_paper["heat"],        
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of biomass in paper production":     {
                "source": intensities_paper["biomass"],     
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of hydrogen in paper production":    {
                "source": intensities_paper["hydrogen"],    
                "unit": "MWh/t", 
                "forecast": False},

            "Activity factor of unspecified paper and pulp": {
                "source": act_unspec_pp,  
                "unit": "-",
                "forecast": False },
            "Share of diesel for unspecified paper and pulp":      {
                "source": fuel_shares_unspec_pp["diesel"],      
                "unit": "% of fuel consumption", 
                "forecast": False},
            "Share of natural gas for unspecified paper and pulp": {
                "source": fuel_shares_unspec_pp["natural_gas"], 
                "unit": "% of fuel consumption", 
                "forecast": False},
            "Share of electricity for unspecified paper and pulp": {
                "source": fuel_shares_unspec_pp["electricity"], 
                "unit": "% of fuel consumption", 
                "forecast": False},
            "Share of coal for unspecified paper and pulp":        {
                "source": fuel_shares_unspec_pp["coal"],       
                "unit": "% of fuel consumption", 
                "forecast": False},
            "Share of heat for unspecified paper and pulp":        {
                "source": fuel_shares_unspec_pp["heat"],        
                "unit": "% of fuel consumption", 
                "forecast": False},
            "Share of biomass for unspecified paper and pulp":     {
                "source": fuel_shares_unspec_pp["biomass"],     
                "unit": "% of fuel consumption", 
                "forecast": False},
            "Share of hydrogen for unspecified paper and pulp":    {
                "source": fuel_shares_unspec_pp["hydrogen"],    
                "unit": "% of fuel consumption", 
                "forecast": False},

            # === Cement production & clinker ===
            "Cement production per year": {
                "source": cement_tpy_2020,      
                "unit": "tons/y",
                "forecast": True,                
            },
            "Clinker-to-cement ratio": {
                "source": clinker_ratio,        
                "unit": "t clinker / t cement",
                "forecast": False,
            },
            "Clinker production per year": {
                "source": clinker_prod,          
                "unit": "tons/y",
                "forecast": False,              
            },

            # === Cement: fuel shares (kiln+process energy)
            "Share of diesel for cement production": {
                "source": cement_fuel_shares["diesel"],
                "unit": "% of Cement production",
                "forecast": False,
            },
            "Share of natural gas for cement production": {
                "source": cement_fuel_shares["natural_gas"],
                "unit": "% of Cement production",
                "forecast": False,
            },
            "Share of electricity for cement production": {
                "source": cement_fuel_shares["electricity"],
                "unit": "% of Cement production",
                "forecast": False,
            },
            "Share of coal for cement production": {
                "source": cement_fuel_shares["coal"],
                "unit": "% of Cement production",
                "forecast": False,
            },
            "Share of heat for cement production": {
                "source": cement_fuel_shares["heat"],
                "unit": "% of Cement production",
                "forecast": False,
            },
            "Share of biomass for cement production": {
                "source": cement_fuel_shares["biomass"],
                "unit": "% of Cement production",
                "forecast": False,
            },
            "Share of hydrogen for cement production": {
                "source": cement_fuel_shares["hydrogen"],
                "unit": "% of Cement production",
                "forecast": False,
            },

            # === Cement: energy intensities (index-based per scenario)
            "Energy intensity of diesel in cement production": {
                "source": cement_intensities["diesel"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of natural gas in cement production": {
                "source": cement_intensities["natural_gas"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of electricity in cement production": {
                "source": cement_intensities["electricity"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of coal in cement production": {
                "source": cement_intensities["coal"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of heat in cement production": {
                "source": cement_intensities["heat"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of biomass in cement production": {
                "source": cement_intensities["biomass"],
                "unit": "MWh/t",
                "forecast": False,
            },
            "Energy intensity of hydrogen in cement production": {
                "source": cement_intensities["hydrogen"],
                "unit": "MWh/t",
                "forecast": False,
            },

            "Activity factor of unspecified non metallic minerals": {
                "source": nmm_activity,   
                "unit": "-",
                "forecast": False,        
            },
            # === Unspecified NMM fuel shares
            "Share of diesel for unspecified non metallic minerals": {
                "source": unspec_nmm_fuel_shares["diesel"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of natural gas for unspecified non metallic minerals": {
                "source": unspec_nmm_fuel_shares["natural_gas"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of electricity for unspecified non metallic minerals": {
                "source": unspec_nmm_fuel_shares["electricity"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of coal for unspecified non metallic minerals": {
                "source": unspec_nmm_fuel_shares["coal"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of heat for unspecified non metallic minerals": {
                "source": unspec_nmm_fuel_shares["heat"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of biomass for unspecified non metallic minerals": {
                "source": unspec_nmm_fuel_shares["biomass"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },
            "Share of hydrogen for unspecified non metallic minerals": {
                "source": unspec_nmm_fuel_shares["hydrogen"],
                "unit": "% of fuel consumption",
                "forecast": False,
            },

            "Energy intensity of unspecified non metallic minerals": {
                "source": nmm_energy_use,  
                "unit": "MWh/y",           
                "forecast": False,         
            },

            "Ammonia production per year": {
                "source": ammonia_prod_source,  
                "column": "production",  
                "unit": "tons/y", 
                "forecast": False
            },
            "Share of SMR + Haber-Bosch": {
                "source": ammonia_share_smr_source,  
                "column": "share_smrhb",       
                "unit": "% of ammonia production", 
                "forecast": False
            },
            "Share of renewable ammonia synthesis": {
                "source": ammonia_share_renew_source,  
                "column": "share_renew",        
                "unit": "% of ammonia production", 
                "forecast": False
            },
            # =========================
            # Ammonia — fuel shares per route
            # =========================
            "Share of diesel for SMR + Haber-Bosch":      {
                "source": fuel_shares_ammonia_smrhb["diesel"],      
                "unit": "% of SMR + Haber-Bosch", 
                "forecast": False},
            "Share of natural gas for SMR + Haber-Bosch": {
                "source": fuel_shares_ammonia_smrhb["natural_gas"], 
                "unit": "% of SMR + Haber-Bosch", 
                "forecast": False},
            "Share of electricity for SMR + Haber-Bosch": {
                "source": fuel_shares_ammonia_smrhb["electricity"], 
                "unit": "% of SMR + Haber-Bosch", 
                "forecast": False},
            "Share of coal for SMR + Haber-Bosch":        {
                "source": fuel_shares_ammonia_smrhb["coal"],       
                "unit": "% of SMR + Haber-Bosch",
                "forecast": False},
            "Share of heat for SMR + Haber-Bosch":        {
                "source": fuel_shares_ammonia_smrhb["heat"],        
                "unit": "% of SMR + Haber-Bosch", 
                "forecast": False},
            "Share of biomass for SMR + Haber-Bosch":     {
                "source": fuel_shares_ammonia_smrhb["biomass"],     
                "unit": "% of SMR + Haber-Bosch", 
                "forecast": False},
            "Share of hydrogen for SMR + Haber-Bosch":    {
                "source": fuel_shares_ammonia_smrhb["hydrogen"],    
                "unit": "% of SMR + Haber-Bosch", 
                "forecast": False},

            "Energy intensity of diesel in SMR + Haber-Bosch":      {
                "source": intens_ammonia_smrhb["diesel"],      
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of natural gas in SMR + Haber-Bosch": {
                "source": intens_ammonia_smrhb["natural_gas"], 
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of electricity in SMR + Haber-Bosch": {
                "source": intens_ammonia_smrhb["electricity"], 
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of coal in SMR + Haber-Bosch":        {
                "source": intens_ammonia_smrhb["coal"],        
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of heat in SMR + Haber-Bosch":        {
                "source": intens_ammonia_smrhb["heat"],        
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of biomass in SMR + Haber-Bosch":     {
                "source": intens_ammonia_smrhb["biomass"],     
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of hydrogen in SMR + Haber-Bosch":    {
                "source": intens_ammonia_smrhb["hydrogen"],    
                "unit": "MWh/t", 
                "forecast": False},


            "Share of diesel for renewable ammonia synthesis":      {
                "source": fuel_shares_ammonia_renew["diesel"],      
                "unit": "% of renewable ammonia synthesis", 
                "forecast": False},
            "Share of natural gas for renewable ammonia synthesis": {
                "source": fuel_shares_ammonia_renew["natural_gas"], 
                "unit": "% of renewable ammonia synthesis", 
                "forecast": False},
            "Share of electricity for renewable ammonia synthesis": {
                "source": fuel_shares_ammonia_renew["electricity"], 
                "unit": "% of renewable ammonia synthesis", 
                "forecast": False},
            "Share of coal for renewable ammonia synthesis":        {
                "source": fuel_shares_ammonia_renew["coal"],        
                "unit": "% of renewable ammonia synthesis", 
                "forecast": False},
            "Share of heat for renewable ammonia synthesis":        {
                "source": fuel_shares_ammonia_renew["heat"],        
                "unit": "% of renewable ammonia synthesis", 
                "forecast": False},
            "Share of biomass for renewable ammonia synthesis":     {
                "source": fuel_shares_ammonia_renew["biomass"],     
                "unit": "% of renewable ammonia synthesis", 
                "forecast": False},
            "Share of hydrogen for renewable ammonia synthesis":    {
                "source": fuel_shares_ammonia_renew["hydrogen"],    
                "unit": "% of renewable ammonia synthesis", 
                "forecast": False},

            "Energy intensity of diesel in renewable ammonia synthesis":      {
                "source": intens_ammonia_renew["diesel"],      
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of natural gas in renewable ammonia synthesis": {
                "source": intens_ammonia_renew["natural_gas"], 
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of electricity in renewable ammonia synthesis": {
                "source": intens_ammonia_renew["electricity"], 
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of coal in renewable ammonia synthesis":        {
                "source": intens_ammonia_renew["coal"],        
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of heat in renewable ammonia synthesis":        {
                "source": intens_ammonia_renew["heat"],        
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of biomass in renewable ammonia synthesis":     {
                "source": intens_ammonia_renew["biomass"],     
                "unit": "MWh/t", 
                "forecast": False},
            "Energy intensity of hydrogen in renewable ammonia synthesis":    {
                "source": intens_ammonia_renew["hydrogen"],    
                "unit": "MWh/t", 
                "forecast": False},
            "High value chemical production per year": {
                "source": hvc_prod_source,
                "unit": "tons/y",
                "forecast": False,},
            "Share of Naphtha cracking for HVC production": {
                "source": hvc_route_shares["Naphtha"],
                "unit": "% of HVC production",
                "forecast": False,},
            "Share of LPG cracking for HVC production": {
                "source": hvc_route_shares["LPG"],
                "unit": "% of HVC production",
                "forecast": False,},
            "Share of Methanol route for HVC production": {
                "source": hvc_route_shares["Methanol"],
                "unit": "% of HVC production",
                "forecast": False,},
            "Share of diesel for Naphtha cracking": {
                "source": fuel_shares_hvc_naphtha["diesel"],
                "unit": "% of Naphtha cracking",
                "forecast": False,},
            "Share of natural gas for Naphtha cracking": {
                "source": fuel_shares_hvc_naphtha["natural_gas"],
                "unit": "% of Naphtha cracking",
                "forecast": False,},
            "Share of electricity for Naphtha cracking": {
                "source": fuel_shares_hvc_naphtha["electricity"],
                "unit": "% of Naphtha cracking",
                "forecast": False,},
            "Share of coal for Naphtha cracking": {
                "source": fuel_shares_hvc_naphtha["coal"],
                "unit": "% of Naphtha cracking",
                "forecast": False,},  
            "Share of heat for Naphtha cracking": {
                "source": fuel_shares_hvc_naphtha["heat"],
                "unit": "% of Naphtha cracking",
                "forecast": False,},  
            "Share of biomass for Naphtha cracking": {
                "source": fuel_shares_hvc_naphtha["biomass"],
                "unit": "% of Naphtha cracking",
                "forecast": False,},
            "Share of hydrogen for Naphtha cracking": {
                "source": fuel_shares_hvc_naphtha["hydrogen"],
                "unit": "% of Naphtha cracking",
                "forecast": False,},
            "Energy intensity of diesel in Naphtha cracking": {
                "source": intens_hvc_naphtha["diesel"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of natural gas in Naphtha cracking": {
                "source": intens_hvc_naphtha["natural_gas"],
                "unit": "MWh/t",
                "forecast": False,},      
            "Energy intensity of electricity in Naphtha cracking": {
                "source": intens_hvc_naphtha["electricity"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of coal in Naphtha cracking": {
                "source": intens_hvc_naphtha["coal"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of heat in Naphtha cracking": {
                "source": intens_hvc_naphtha["heat"],
                "unit": "MWh/t",
                "forecast": False,},  
            "Energy intensity of biomass in Naphtha cracking": {
                "source": intens_hvc_naphtha["biomass"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of hydrogen in Naphtha cracking": {
                "source": intens_hvc_naphtha["hydrogen"],
                "unit": "MWh/t",
                "forecast": False,},
            "Share of diesel for LPG cracking": {
                "source": fuel_shares_hvc_lpg["diesel"],
                "unit": "% of LPG cracking",
                "forecast": False,},
            "Share of natural gas for LPG cracking": {
                "source": fuel_shares_hvc_lpg["natural_gas"],
                "unit": "% of LPG cracking",
                "forecast": False,},
            "Share of electricity for LPG cracking": {
                "source": fuel_shares_hvc_lpg["electricity"],
                "unit": "% of LPG cracking",
                "forecast": False,},
            "Share of coal for LPG cracking": {
                "source": fuel_shares_hvc_lpg["coal"],
                "unit": "% of LPG cracking",
                "forecast": False,},
            "Share of heat for LPG cracking": {
                "source": fuel_shares_hvc_lpg["heat"],
                "unit": "% of LPG cracking",
                "forecast": False },
            "Share of biomass for LPG cracking": {
                "source": fuel_shares_hvc_lpg["biomass"],
                "unit": "% of LPG cracking",
                "forecast": False,},
            "Share of hydrogen for LPG cracking": {
                "source": fuel_shares_hvc_lpg["hydrogen"],
                "unit": "% of LPG cracking",
                "forecast": False,},
            "Energy intensity of diesel in LPG cracking": {
                "source": intens_hvc_lpg["diesel"],
                "unit": "MWh/t",
                "forecast": False,},  
            "Energy intensity of natural gas in LPG cracking": {
                "source": intens_hvc_lpg["natural_gas"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of electricity in LPG cracking": {
                "source": intens_hvc_lpg["electricity"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of coal in LPG cracking": {
                "source": intens_hvc_lpg["coal"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of heat in LPG cracking": {
                "source": intens_hvc_lpg["heat"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of biomass in LPG cracking": {
                "source": intens_hvc_lpg["biomass"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of hydrogen in LPG cracking": {
                "source": intens_hvc_lpg["hydrogen"],
                "unit": "MWh/t",
                "forecast": False,},
            "Share of diesel for Methanol route": {
                "source": fuel_shares_hvc_meth["diesel"],
                "unit": "% of Methanol route",
                "forecast": False,},
            "Share of natural gas for Methanol route": {
                "source": fuel_shares_hvc_meth["natural_gas"],
                "unit": "% of Methanol route",
                "forecast": False,},  
            "Share of electricity for Methanol route": {
                "source": fuel_shares_hvc_meth["electricity"],
                "unit": "% of Methanol route",
                "forecast": False,},
            "Share of coal for Methanol route": {
                "source": fuel_shares_hvc_meth["coal"],
                "unit": "% of Methanol route",
                "forecast": False,},
            "Share of heat for Methanol route": {
                "source": fuel_shares_hvc_meth["heat"],
                "unit": "% of Methanol route",
                "forecast": False,},
            "Share of biomass for Methanol route": {
                "source": fuel_shares_hvc_meth["biomass"],
                "unit": "% of Methanol route",
                "forecast": False,},
            "Share of hydrogen for Methanol route": {
                "source": fuel_shares_hvc_meth["hydrogen"],
                "unit": "% of Methanol route",
                "forecast": False,},
            "Energy intensity of diesel in Methanol route": {
                "source": intens_hvc_meth["diesel"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of natural gas in Methanol route": {
                "source": intens_hvc_meth["natural_gas"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of electricity in Methanol route": {
                "source": intens_hvc_meth["electricity"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of coal in Methanol route": {
                "source": intens_hvc_meth["coal"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of heat in Methanol route": {
                "source": intens_hvc_meth["heat"],
                "unit": "MWh/t",
                "forecast": False, },
            "Energy intensity of biomass in Methanol route": {
                "source": intens_hvc_meth["biomass"],
                "unit": "MWh/t",
                "forecast": False,},
            "Energy intensity of hydrogen in Methanol route": {
                "source": intens_hvc_meth["hydrogen"],
                "unit": "MWh/t",
                "forecast": False,},
            "Activity factor of unspecified chemicals": {
                "source": act_unspec_chem,
                "unit": "-",
                "forecast": False,},
            "Share of diesel for unspecified chemicals" : {
                "source": share_fuel_unspecified["diesel"],
                "unit": "% of fuel consumption",
                "forecast": False,},  
            "Share of natural gas for unspecified chemicals" : {
                "source": share_fuel_unspecified["natural_gas"],
                "unit": "% of fuel consumption",
                "forecast": False,},
            "Share of electricity for unspecified chemicals" : {
                "source": share_fuel_unspecified["electricity"],
                "unit": "% of fuel consumption",
                "forecast": False,},
            "Share of coal for unspecified chemicals" : {
                "source": share_fuel_unspecified["coal"],
                "unit": "% of fuel consumption",
                "forecast": False, },
            "Share of heat for unspecified chemicals" : {
                "source": share_fuel_unspecified["heat"],
                "unit": "% of fuel consumption",
                "forecast": False,},
            "Share of biomass for unspecified chemicals" : {
                "source": share_fuel_unspecified["biomass"],
                "unit": "% of fuel consumption",
                "forecast": False,},
            "Share of hydrogen for unspecified chemicals" : {
                "source": share_fuel_unspecified["hydrogen"],
                "unit": "% of fuel consumption",
                "forecast": False,},
            
            # === Food and tobacco (unspecified) ===
            "Final energy of food and tobacco": {
                "source": results["food and tobacco"]["total"],
                "unit": "GWh",
                "forecast": True
            },
            "Share of oil for unspecified food and tobacco": {
                "source": results["food and tobacco"]["shares"]["oil"],
                "unit": "%", 
                "forecast": False
            },
            "Share of gas for unspecified food and tobacco": {
                "source": results["food and tobacco"]["shares"]["gas"],
                "unit": "%", 
                "forecast": False
            },
            "Share of electricity for unspecified food and tobacco": {
                "source": results["food and tobacco"]["shares"]["electricity"],
                "unit": "%", 
                "forecast": False
            },
            "Share of coal for unspecified food and tobacco": {
                "source": results["food and tobacco"]["shares"]["coal"],
                "unit": "%", 
                "forecast": False
            },
            "Share of biomass for unspecified food and tobacco": {
                "source": results["food and tobacco"]["shares"]["biomass"],
                "unit": "%", 
                "forecast": False
            },
            "Share of hydrogen for unspecified food and tobacco": {
                "source": results["food and tobacco"]["shares"]["hydrogen"],
                "unit": "%", 
                "forecast": False
            },
            "Share of ammonia for unspecified food and tobacco": {
                "source": results["food and tobacco"]["shares"]["ammonia"],
                "unit": "%",
                "forecast": False
            },
            "Share of methanol for unspecified food and tobacco": {
                "source": results["food and tobacco"]["shares"]["methanol"],
                "unit": "%", 
                "forecast": False
            },
             "Share of steel for unspecified food and tobacco": {
                "source": results["food and tobacco"]["shares"]["steel"],
                "unit": "%", 
                "forecast": False
             },

            # construction 
            "Final energy of construction": {
                "source": results["construction"]["total"], 
                "unit": "GWh",
                "forecast": True
            },
            "Share of oil for unspecified construction": {
                "source": results["construction"]["shares"]["oil"],
                "unit": "%", 
                "forecast": False
            },      
            "Share of gas for unspecified construction": {
                "source": results["construction"]["shares"]["gas"],
                "unit": "%", 
                "forecast": False
            },
            "Share of electricity for unspecified construction": {
                "source": results["construction"]["shares"]["electricity"],
                "unit": "%", 
                "forecast": False
            },
            "Share of coal for unspecified construction": {
                "source": results["construction"]["shares"]["coal"],
                "unit": "%", 
                "forecast": False
            },
            "Share of biomass for unspecified construction": {
                "source": results["construction"]["shares"]["biomass"],
                "unit": "%", 
                "forecast": False
            },
            "Share of hydrogen for unspecified construction": {
                "source": results["construction"]["shares"]["hydrogen"],
                "unit": "%", 
                "forecast": False
            },
            "Share of ammonia for unspecified construction": {
                "source": results["construction"]["shares"]["ammonia"],
                "unit": "%",
                "forecast": False
            },
            "Share of methanol for unspecified construction": {
                "source": results["construction"]["shares"]["methanol"],
                "unit": "%", 
                "forecast": False
            },
            "Share of steel for unspecified construction": {
                "source": results["construction"]["shares"]["steel"],
                "unit": "%", 
                "forecast": False
            },

            # machinery
            "Final energy of machinery": {
                "source": results["machinery"]["total"], 
                "unit": "GWh",
                "forecast": True
            },
            "Share of oil for unspecified machinery": {
                "source": results["machinery"]["shares"]["oil"],
                "unit": "%", 
                "forecast": False
            },
            "Share of gas for unspecified machinery": {
                "source": results["machinery"]["shares"]["gas"],
                "unit": "%", 
                "forecast": False
            },
            "Share of electricity for unspecified machinery": {
                "source": results["machinery"]["shares"]["electricity"],
                "unit": "%", 
                "forecast": False
            },
            "Share of coal for unspecified machinery": {
                "source": results["machinery"]["shares"]["coal"],
                "unit": "%", 
                "forecast": False
            },
            "Share of biomass for unspecified machinery": {
                "source": results["machinery"]["shares"]["biomass"],
                "unit": "%", 
                "forecast": False
            },
            "Share of hydrogen for unspecified machinery": {
                "source": results["machinery"]["shares"]["hydrogen"],
                "unit": "%", 
                "forecast": False
            },
            "Share of ammonia for unspecified machinery": {
                "source": results["machinery"]["shares"]["ammonia"],
                "unit": "%",
                "forecast": False
            },
            "Share of methanol for unspecified machinery": {
                "source": results["machinery"]["shares"]["methanol"],
                "unit": "%", 
                "forecast": False
            },
            "Share of steel for unspecified machinery": {
                "source": results["machinery"]["shares"]["steel"],
                "unit": "%", 
                "forecast": False
            },

            # mining and quarrying
            "Final energy of mining and quarrying": {
                "source": results["mining and quarrying"]["total"], 
                "unit": "GWh",
                "forecast": True
            },
            "Share of oil for unspecified mining and quarrying": {
                "source": results["mining and quarrying"]["shares"]["oil"],
                "unit": "%", 
                "forecast": False
            },
            "Share of gas for unspecified mining and quarrying": {
                "source": results["mining and quarrying"]["shares"]["gas"],
                "unit": "%", 
                "forecast": False
            }, 
            "Share of electricity for unspecified mining and quarrying": {
                "source": results["mining and quarrying"]["shares"]["electricity"],
                "unit": "%", 
                "forecast": False
            },
            "Share of coal for unspecified mining and quarrying": {
                "source": results["mining and quarrying"]["shares"]["coal"],
                "unit": "%", 
                "forecast": False
            },
            "Share of biomass for unspecified mining and quarrying": {
                "source": results["mining and quarrying"]["shares"]["biomass"],
                "unit": "%", 
                "forecast": False
            },
            "Share of hydrogen for unspecified mining and quarrying": {
                "source": results["mining and quarrying"]["shares"]["hydrogen"],
                "unit": "%", 
                "forecast": False
            },
            "Share of ammonia for unspecified mining and quarrying": {
                "source": results["mining and quarrying"]["shares"]["ammonia"],
                "unit": "%",
                "forecast": False
            },
            "Share of methanol for unspecified mining and quarrying": {
                "source": results["mining and quarrying"]["shares"]["methanol"],
                "unit": "%", 
                "forecast": False
            },
            "Share of steel for unspecified mining and quarrying": {
                "source": results["mining and quarrying"]["shares"]["steel"],
                "unit": "%", 
                "forecast": False
            },
            
            # Non-ferrous metals
            "Final energy of non-ferrous metals": {
                "source": results["non-ferrous metals"]["total"], 
                "unit": "GWh",
                "forecast": True
            },
            "Share of oil for unspecified non-ferrous metals": {    
                "source": results["non-ferrous metals"]["shares"]["oil"],
                "unit": "%", 
                "forecast": False
            },
            "Share of gas for unspecified non-ferrous metals": {
                "source": results["non-ferrous metals"]["shares"]["gas"],
                "unit": "%", 
                "forecast": False
            },
            "Share of electricity for unspecified non-ferrous metals": {
                "source": results["non-ferrous metals"]["shares"]["electricity"],
                "unit": "%", 
                "forecast": False
            },
            "Share of coal for unspecified non-ferrous metals": {
                "source": results["non-ferrous metals"]["shares"]["coal"],
                "unit": "%", 
                "forecast": False
            },
            "Share of biomass for unspecified non-ferrous metals": {
                "source": results["non-ferrous metals"]["shares"]["biomass"],
                "unit": "%", 
                "forecast": False
            },
            "Share of hydrogen for unspecified non-ferrous metals": {
                "source": results["non-ferrous metals"]["shares"]["hydrogen"],
                "unit": "%", 
                "forecast": False
            },
            "Share of ammonia for unspecified non-ferrous metals": {
                "source": results["non-ferrous metals"]["shares"]["ammonia"],
                "unit": "%",
                "forecast": False
            },
            "Share of methanol for unspecified non-ferrous metals": {
                "source": results["non-ferrous metals"]["shares"]["methanol"],
                "unit": "%", 
                "forecast": False
            },
            "Share of steel for unspecified non-ferrous metals": {
                "source": results["non-ferrous metals"]["shares"]["steel"],
                "unit": "%", 
                "forecast": False
            },


            # textile and leather
            "Final energy of textile and leather": {
                "source": results["textile and leather"]["total"], 
                "unit": "GWh",
                "forecast": True
            },
            "Share of oil for unspecified textile and leather": {
                "source": results["textile and leather"]["shares"]["oil"],
                "unit": "%", 
                "forecast": False
            },
            "Share of gas for unspecified textile and leather": {
                "source": results["textile and leather"]["shares"]["gas"],
                "unit": "%", 
                "forecast": False
            },
            "Share of electricity for unspecified textile and leather": {
                "source": results["textile and leather"]["shares"]["electricity"],
                "unit": "%", 
                "forecast": False
            },
            "Share of coal for unspecified textile and leather": {
                "source": results["textile and leather"]["shares"]["coal"],
                "unit": "%", 
                "forecast": False
            },
            "Share of biomass for unspecified textile and leather": {
                "source": results["textile and leather"]["shares"]["biomass"],
                "unit": "%", 
                "forecast": False
            },
            "Share of hydrogen for unspecified textile and leather": {
                "source": results["textile and leather"]["shares"]["hydrogen"],
                "unit": "%", 
                "forecast": False
            },
            "Share of ammonia for unspecified textile and leather": {
                "source": results["textile and leather"]["shares"]["ammonia"],
                "unit": "%",
                "forecast": False
            },
            "Share of methanol for unspecified textile and leather": {
                "source": results["textile and leather"]["shares"]["methanol"],
                "unit": "%", 
                "forecast": False
            },
            "Share of steel for unspecified textile and leather": {
                "source": results["textile and leather"]["shares"]["steel"],
                "unit": "%", 
                "forecast": False
            },
             
            # transport equipment
            "Final energy of transport equipment": {
                "source": results["transport equipment"]["total"], 
                "unit": "GWh",
                "forecast": True
            },
            "Share of oil for unspecified transport equipment": {
                "source": results["transport equipment"]["shares"]["oil"],
                "unit": "%", 
                "forecast": False
            },
            "Share of gas for unspecified transport equipment": {
                "source": results["transport equipment"]["shares"]["gas"],
                "unit": "%", 
                "forecast": False
            },
            "Share of electricity for unspecified transport equipment": {
                "source": results["transport equipment"]["shares"]["electricity"],
                "unit": "%", 
                "forecast": False
            },
            "Share of coal for unspecified transport equipment": {
                "source": results["transport equipment"]["shares"]["coal"],
                "unit": "%", 
                "forecast": False
            },
            "Share of biomass for unspecified transport equipment": {
                "source": results["transport equipment"]["shares"]["biomass"],
                "unit": "%", 
                "forecast": False
            },
            "Share of hydrogen for unspecified transport equipment": {
                "source": results["transport equipment"]["shares"]["hydrogen"],
                "unit": "%", 
                "forecast": False
            },
            "Share of ammonia for unspecified transport equipment": {
                "source": results["transport equipment"]["shares"]["ammonia"],
                "unit": "%",
                "forecast": False
            },
            "Share of methanol for unspecified transport equipment": {
                "source": results["transport equipment"]["shares"]["methanol"],
                "unit": "%", 
                "forecast": False
            },
            "Share of steel for unspecified transport equipment": {
                "source": results["transport equipment"]["shares"]["steel"],
                "unit": "%", 
                "forecast": False
            },

            # wood and wood products
            "Final energy of wood and wood products": {
                "source": results["wood and wood products"]["total"], 
                "unit": "GWh",
                "forecast": True
            },
            "Share of oil for unspecified wood and wood products": {    
                "source": results["wood and wood products"]["shares"]["oil"],
                "unit": "%", 
                "forecast": False
            },
            "Share of gas for unspecified wood and wood products": {
                "source": results["wood and wood products"]["shares"]["gas"],
                "unit": "%", 
                "forecast": False
            },
            "Share of electricity for unspecified wood and wood products": {
                "source": results["wood and wood products"]["shares"]["electricity"],
                "unit": "%", 
                "forecast": False
            },
            "Share of coal for unspecified wood and wood products": {
                "source": results["wood and wood products"]["shares"]["coal"],
                "unit": "%", 
                "forecast": False
            },
            "Share of biomass for unspecified wood and wood products": {
                "source": results["wood and wood products"]["shares"]["biomass"],
                "unit": "%", 
                "forecast": False
            },
            "Share of hydrogen for unspecified wood and wood products": {
                "source": results["wood and wood products"]["shares"]["hydrogen"],
                "unit": "%", 
                "forecast": False
            },
            "Share of ammonia for unspecified wood and wood products": {
                "source": results["wood and wood products"]["shares"]["ammonia"],
                "unit": "%",
                "forecast": False
            },
            "Share of methanol for unspecified wood and wood products": {
                "source": results["wood and wood products"]["shares"]["methanol"],
                "unit": "%", 
                "forecast": False
            },
            "Share of steel for unspecified wood and wood products": {
                "source": results["wood and wood products"]["shares"]["steel"],
                "unit": "%", 
                "forecast": False
            },
         }
        columns = ["Metric", str(base_year)]
        columns += [f"{yr}_{sc}" for yr in target_years for sc in scenarios]
        columns += ["Units"]

        rows = []


        for name, meta in metrics.items():
            unit = meta["unit"]
            source = meta["source"]
            base_val = None
            scenario_vals = {}

            # --- 2.a DataFrame source ---
            if isinstance(source, pd.DataFrame):
                df = source.copy()
                if "Country" in df.columns:
                    df = df[df["Country"] == country]
                elif "country" in df.columns:
                    df = df[df["country"] == country]


                if "Year" in df.columns or "year" in df.columns:
                    ycol = "Year" if "Year" in df.columns else "year"
                    df = df.sort_values(ycol)
                    colname = meta.get("column")
                    if colname:
                        years_clean = pd.to_numeric(df[ycol], errors="coerce").dropna()

                        # === FIX START ===
                        if years_clean.empty:
                            # If no valid years, treat as missing data. Do NOT return.
                            print(f" Info: Skipping interpolation — no valid years in '{ycol}' for {name}")
                            base_val = None
                            scenario_vals = {f"{y}_{sc}": None for y in target_years for sc in scenarios}
                        else:
                            # Proceed with normal interpolation
                            years_full = range(int(years_clean.min()), int(years_clean.max()) + 1)
                            df_interp = (
                                df.set_index(ycol)[[colname]]
                                .reindex(years_full)
                                .interpolate().ffill().bfill()
                            )
                            by = int(base_year)
                            base_val = float(df_interp.loc[by, colname]) if by in df_interp.index else None
                            for y in target_years:
                                v = float(df_interp.loc[y, colname]) if y in df_interp.index else None
                                for sc in scenarios:
                                    scenario_vals[f"{y}_{sc}"] = v

                    else:
                        num_cols = df.select_dtypes(include="number").columns
                        if len(num_cols):
                            c0 = num_cols[0]
                            years_clean = pd.to_numeric(df[ycol], errors="coerce").dropna()
                            if years_clean.empty:
                                print(f" Info: Skipping interpolation — no valid years in '{ycol}' for {name}")
                                base_val = None
                                scenario_vals = {f"{y}_{sc}": None for y in target_years for sc in scenarios}
                            else:
                                years_full = range(int(years_clean.min()), int(years_clean.max()) + 1)


                                df_interp = (
                                    df.set_index(ycol)[[c0]]
                                    .reindex(years_full)
                                    .interpolate().ffill().bfill()
                                )

                                by = int(base_year)
                                base_val = float(df_interp.loc[by, c0]) if by in df_interp.index else None
                                for y in target_years:
                                    val_y = float(df_interp.loc[y, c0]) if y in df_interp.index else None
                                    for sc in scenarios:
                                        scenario_vals[f"{y}_{sc}"] = val_y
                            by = int(base_year)
                            base_val = float(df_interp.loc[by, c0]) if by in df_interp.index else None
                            for y in target_years:
                                val_y = float(df_interp.loc[y, c0]) if y in df_interp.index else None
                                for sc in scenarios:
                                    scenario_vals[f"{y}_{sc}"] = val_y
                        else:
                            base_val = None
                            scenario_vals = {f"{y}_{sc}": None for y in target_years for sc in scenarios}


                elif any(str(c).isdigit() for c in df.columns):
                    if df.empty:
                        base_val = None
                        scenario_vals = {f"{y}_{sc}": None for y in target_years for sc in scenarios}
                    else:
                        series = {}
                        for c in df.columns:
                            cs = str(c)
                            if cs.isdigit():
                                y = int(cs)
                                try:
                                    series[y] = float(df.iloc[0][c])
                                except Exception:
                                    pass
                        base_val = _interp_at(series, base_year)
                        scenario_vals = {}
                        for y in target_years:
                            vy = _interp_at(series, y)
                            for sc in scenarios:
                                scenario_vals[f"{y}_{sc}"] = vy



            # --- 2.b dict source ---
            elif isinstance(source, dict):
                base_series = {}
                for y, val in source.items():
                    try:
                        yi = int(y)
                    except Exception:
                        continue
                    v0 = _get_value_by_index(val, 0)
                    if v0 is not None:
                        base_series[yi] = v0
                base_val = _interp_at(base_series, base_year)
                scenario_vals = {}
                for idx, sc in enumerate(scenarios):
                    series_i = {}
                    for y, val in source.items():
                        try:
                            yi = int(y)
                        except Exception:
                            continue
                        vi = _get_value_by_index(val, idx)
                        if vi is not None:
                            series_i[yi] = vi
                    for y in target_years:
                        scenario_vals[f"{y}_{sc}"] = _interp_at(series_i, y)


            # --- 2.c scalar source ---
            elif isinstance(source, (int, float)):
                base_val = source
                scenario_vals = {f"{y}_{sc}": source for y in target_years for sc in scenarios}
            else:
                base_val = None
                scenario_vals = {f"{y}_{sc}": None for y in target_years for sc in scenarios}



            # --- SPECIAL CASE: Unspecified NMM activity factor (compute & append immediately) ---

            if name == "Activity factor of unspecified non metallic minerals" and meta.get("forecast", False):
                base_val = float(cement_tpy_2020)
                cagr_cfg = get_metric_cagr_cfg_from_excel(
                industry_cagr_excel,
                country,
                name)
                nmm_path = activity_factor_unspecified_nmm(
                    base_value=base_val,
                    base_year=base_year,
                    target_years=target_years,
                    cagr_cfg=cagr_cfg,
                    scenarios=scenarios,
                    use_profile=False,

                )
                scenario_vals = {}
                for y in target_years:
                    for sc in scenarios:
                        scenario_vals[f"{y}_{sc}"] = nmm_path.get(y, {}).get(sc)

                result_expanded = {base_year: base_val}
                result_expanded.update(scenario_vals)
                row = {"Metric": name, str(base_year): base_val, "Units": unit}
                row.update({k: v for k, v in result_expanded.items() if k != base_year})
                rows.append(row)

                continue  # important: only for this special case



            # --- GENERIC FORECAST / OUTPUT for all other metrics ---

            result_expanded = {base_year: base_val}
            
            if meta.get("forecast", True) and base_val is not None:
                # 1. Map the specific metric name to the category name in your Excel
                search_name = get_mapped_config_name(name)

                # 2. Use that search_name to get the CAGR configuration
                metric_cfg = get_metric_cagr_cfg_from_excel(industry_cagr_excel, country, search_name)

                # pull a simple history if DataFrame-based
                hist_series = None
                if isinstance(source, pd.DataFrame):
                    dfh = source.copy()
                    if "Country" in dfh.columns:
                        dfh = dfh[dfh["Country"] == country]
                    elif "country" in dfh.columns:
                        dfh = dfh[dfh["country"] == country]
                    if not dfh.empty:
                        s = {}
                        for c in dfh.columns:
                            cs = str(c)
                            if cs.isdigit():
                                try:
                                    s[int(cs)] = float(dfh.iloc[0][c])
                                except Exception:
                                    pass
                        hist_series = s if s else None


                if name == "Steel production per year":
                    last_obs_year = base_year
                    last_obs_val  = base_val
                elif name == "Activity factor of unspecified iron and steel":
                    last_obs_year = base_year
                    last_obs_val  = base_val
                elif name == "Paper production per year":
                    last_obs_year = base_year 
                    last_obs_val  = base_val
                elif name == "Pulp production per year":
                    last_obs_year = base_year 
                    last_obs_val  = base_val
                elif hist_series:
                    last_obs_year = max(hist_series.keys())
                    last_obs_val  = hist_series[last_obs_year]
                    for y in target_years:
                        if y <= last_obs_year and f"{y}_{scenarios[0]}" in scenario_vals:
                            for sc in scenarios:
                                result_expanded[f"{y}_{sc}"] = scenario_vals.get(f"{y}_{sc}")
                else:
                    last_obs_year = base_year
                    last_obs_val  = base_val


                future_years = [y for y in target_years if y > last_obs_year]
                if future_years:
                    # We use the new library function here
                    grown = expand_with_cagr_smooth(
                        base_value=last_obs_val,
                        cagr_table=metric_cfg,
                        base_year=last_obs_year,
                        target_years=future_years,
                        scenarios=scenarios
                    )
                    
                    # Optional: Add this to see if it's working in your console
                    #print(f"Metric: {name} | Base {last_obs_year}: {last_obs_val} | 2030 result: {grown.get('2030_Baseline')}")
                    
                    result_expanded.update(grown)
            else:
                for k, v in scenario_vals.items():
                    result_expanded[k] = v


            row = {"Metric": name, str(base_year): base_val, "Units": unit}
            row.update({k: v for k, v in result_expanded.items() if k != base_year})
            rows.append(row)

            continue

        validate_fuel_shares(rows, base_year, target_years, scenarios)
        # after metrics loop
        df_out = pd.DataFrame(rows)
        df_out = df_out.reindex(columns=columns)
        
        # Sort rows by METRIC_ORDER
        metric_order_map = {name: i for i, name in enumerate(METRIC_ORDER)}
        df_out["__sort_key__"] = df_out["Metric"].map(lambda x: metric_order_map.get(x, 9999))
        df_out = df_out.sort_values("__sort_key__").drop(columns=["__sort_key__"])
        
        out_path = output_root / f"{country}_Output.csv"
        #print("DEBUG output_root:", output_root)
        #print("DEBUG type(output_root):", type(output_root))
        df_out.to_csv(out_path, index=False, encoding='utf-8')
        print(f" Saved: {out_path}")

if __name__ == "__main__": 
    main()