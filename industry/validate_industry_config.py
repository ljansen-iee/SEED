"""
Validation script for INDUSTRY_CONFIG.csv and derivative files.

Checks:
1. All expected files exist
2. Row counts match expectations
3. No missing data
4. Proper structure and columns
5. Year/scenario/country coverage
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output_data"
CONFIG_DIR = OUTPUT_DIR / "CONFIG"

# Expected files
EXPECTED_FILES = {
    "INDUSTRY_CONFIG.csv": CONFIG_DIR / "INDUSTRY_CONFIG.csv",
    "steel_intensity_projections.csv": OUTPUT_DIR / "steel_intensity_projections.csv",
    "ammonia_intensity_projections.csv": OUTPUT_DIR / "ammonia_intensity_projections.csv",
    "steel_volumes.csv": OUTPUT_DIR / "steel_volumes.csv",
    "ammonia_volumes.csv": OUTPUT_DIR / "ammonia_volumes.csv",
}

# Test configuration
COUNTRIES = ['Morocco', 'Egypt', 'South Africa', 'Namibia']
BASE_YEAR = 2020
TARGET_YEARS = [2030, 2035, 2040, 2045, 2050]
ALL_YEARS = [BASE_YEAR] + TARGET_YEARS
SCENARIOS = ["BAU", "Progressive", "Optimistic"]


def check_file_exists(name: str, path: Path) -> bool:
    """Check if file exists."""
    if path.exists():
        print(f"✅ {name:40s} EXISTS")
        return True
    else:
        print(f"❌ {name:40s} MISSING")
        return False


def validate_industry_config(df: pd.DataFrame) -> Dict[str, bool]:
    """Validate main INDUSTRY_CONFIG.csv."""
    results = {}
    
    # Check columns
    expected_cols = ['industry_sector', 'type', 'metric name', 'year', 'scenario', 'units'] + COUNTRIES
    missing_cols = set(expected_cols) - set(df.columns)
    if not missing_cols:
        print(f"  ✅ All expected columns present")
        results['columns'] = True
    else:
        print(f"  ❌ Missing columns: {missing_cols}")
        results['columns'] = False
    
    # Check sectors
    sectors = df['industry_sector'].unique()
    print(f"  ✅ Sectors: {list(sectors)}")
    results['sectors'] = 'iron and steel' in sectors and 'ammonia' in sectors
    
    # Check row counts per sector
    steel_rows = len(df[df['industry_sector'] == 'iron and steel'])
    ammonia_rows = len(df[df['industry_sector'] == 'ammonia'])
    print(f"  ✅ Steel rows: {steel_rows}")
    print(f"  ✅ Ammonia rows: {ammonia_rows}")
    print(f"  ✅ Total rows: {len(df)}")
    results['row_count'] = len(df) > 1000
    
    # Check for NaN values in data columns (excluding CAGR rows and share rows)
    # - CAGR rows have year strings like "2020-2030" and intentionally have NaN for periods
    # - Share rows may have NaN for fuels not used by that route (e.g., hydrogen share for conventional routes)
    critical_rows = df[(df['type'] != 'cagr') & (df['type'] != 'share')]
    data_cols = COUNTRIES
    nan_counts = critical_rows[data_cols].isna().sum().sum()
    
    # Also show share NaN counts separately for info
    share_rows = df[df['type'] == 'share']
    share_nan_counts = share_rows[data_cols].isna().sum().sum()
    
    if nan_counts == 0:
        print(f"  ✅ No NaN values in critical data columns")
        print(f"  ℹ️  Share rows have {share_nan_counts} NaN values (expected for unused fuels)")
        results['no_nan'] = True
    else:
        print(f"  ⚠️  {nan_counts} NaN values found in critical rows")
        print(f"  ℹ️  Share rows have {share_nan_counts} additional NaN values")
        results['no_nan'] = False
    
    # Check year coverage (excluding CAGR period rows)
    year_rows = df[df['year'].apply(lambda x: isinstance(x, int) or (isinstance(x, str) and x.isdigit()))]
    years_present = sorted([int(y) for y in year_rows['year'].unique()])
    if set(ALL_YEARS).issubset(set(years_present)):
        print(f"  ✅ All years present: {years_present}")
        results['years'] = True
    else:
        print(f"  ⚠️  Missing years. Expected: {ALL_YEARS}, Got: {years_present}")
        results['years'] = False
    
    # Show CAGR period rows separately
    cagr_periods = df[df['type'] == 'cagr']['year'].unique()
    print(f"  ✅ CAGR periods: {list(cagr_periods)}")
    
    # Check scenario coverage
    scenarios_present = sorted(df['scenario'].unique())
    if set(SCENARIOS) == set(scenarios_present):
        print(f"  ✅ All scenarios present: {scenarios_present}")
        results['scenarios'] = True
    else:
        print(f"  ⚠️  Scenario mismatch. Expected: {SCENARIOS}, Got: {scenarios_present}")
        results['scenarios'] = False
    
    return results


def validate_intensity_projections(df: pd.DataFrame, sector: str) -> Dict[str, bool]:
    """Validate intensity projection files."""
    results = {}
    
    # Check columns
    expected_cols = ['route', 'scenario', 'year', 'units'] + COUNTRIES
    missing_cols = set(expected_cols) - set(df.columns)
    if not missing_cols:
        print(f"  ✅ All expected columns present")
        results['columns'] = True
    else:
        print(f"  ❌ Missing columns: {missing_cols}")
        results['columns'] = False
    
    # Check routes
    routes = df['route'].unique()
    print(f"  ✅ Routes: {len(routes)} unique routes")
    for route in routes:
        print(f"      - {route}")
    
    # Check years
    years_present = sorted(df['year'].unique())
    if set(ALL_YEARS).issubset(set(years_present)):
        print(f"  ✅ All years present: {len(years_present)} years")
        results['years'] = True
    else:
        print(f"  ⚠️  Missing years")
        results['years'] = False
    
    # Check scenarios
    scenarios_present = sorted(df['scenario'].unique())
    if set(SCENARIOS) == set(scenarios_present):
        print(f"  ✅ All scenarios present: {scenarios_present}")
        results['scenarios'] = True
    else:
        print(f"  ⚠️  Scenario mismatch")
        results['scenarios'] = False
    
    # Check for reasonable intensity values (should be > 0 and < 1000 MWh/t)
    data_cols = COUNTRIES
    min_val = df[data_cols].min().min()
    max_val = df[data_cols].max().max()
    if 0 < min_val and max_val < 1000:
        print(f"  ✅ Intensity values reasonable: {min_val:.2f} - {max_val:.2f} MWh/t")
        results['values'] = True
    else:
        print(f"  ⚠️  Intensity values may be incorrect: {min_val:.2f} - {max_val:.2f} MWh/t")
        results['values'] = False
    
    print(f"  ✅ Total rows: {len(df)}")
    
    return results


def validate_volumes(df: pd.DataFrame, sector: str) -> Dict[str, bool]:
    """Validate volume files."""
    results = {}
    
    print(f"  ✅ Columns: {list(df.columns)}")
    print(f"  ✅ Total rows: {len(df)}")
    
    # Check years
    years_present = sorted(df['year'].unique())
    print(f"  ✅ Years: {len(years_present)} years")
    
    # Check scenarios
    if sector == "steel":
        scenarios_present = sorted(df['scenario'].unique())
        if set(SCENARIOS) == set(scenarios_present):
            print(f"  ✅ All scenarios present: {scenarios_present}")
            results['scenarios'] = True
        else:
            print(f"  ⚠️  Scenario mismatch")
            results['scenarios'] = False
    elif sector == "ammonia":
        # Ammonia uses 'path' column with different scenario names (slow_mover, mid_speed, fast_track)
        if 'path' in df.columns:
            scenarios_present = sorted(df['path'].unique())
            print(f"  ✅ Ammonia paths: {scenarios_present}")
            results['scenarios'] = True
        else:
            print(f"  ⚠️  'path' column not found")
            results['scenarios'] = False
    
    results['row_count'] = len(df) > 10
    
    return results


def main():
    print("=" * 80)
    print("INDUSTRY CONFIG VALIDATION")
    print("=" * 80)
    
    all_results = {}
    
    # 1. Check file existence
    print("\n1️⃣  FILE EXISTENCE")
    print("-" * 80)
    for name, path in EXPECTED_FILES.items():
        exists = check_file_exists(name, path)
        all_results[f"exists_{name}"] = exists
    
    # 2. Validate INDUSTRY_CONFIG.csv
    print("\n2️⃣  INDUSTRY_CONFIG.csv VALIDATION")
    print("-" * 80)
    try:
        df_config = pd.read_csv(EXPECTED_FILES["INDUSTRY_CONFIG.csv"])
        config_results = validate_industry_config(df_config)
        all_results.update({f"config_{k}": v for k, v in config_results.items()})
    except Exception as e:
        print(f"  ❌ Error loading INDUSTRY_CONFIG.csv: {e}")
        all_results['config_load'] = False
    
    # 3. Validate steel_intensity_projections.csv
    print("\n3️⃣  STEEL INTENSITY PROJECTIONS VALIDATION")
    print("-" * 80)
    try:
        df_steel_int = pd.read_csv(EXPECTED_FILES["steel_intensity_projections.csv"])
        steel_int_results = validate_intensity_projections(df_steel_int, "steel")
        all_results.update({f"steel_int_{k}": v for k, v in steel_int_results.items()})
    except Exception as e:
        print(f"  ❌ Error loading steel_intensity_projections.csv: {e}")
        all_results['steel_int_load'] = False
    
    # 4. Validate ammonia_intensity_projections.csv
    print("\n4️⃣  AMMONIA INTENSITY PROJECTIONS VALIDATION")
    print("-" * 80)
    try:
        df_amm_int = pd.read_csv(EXPECTED_FILES["ammonia_intensity_projections.csv"])
        amm_int_results = validate_intensity_projections(df_amm_int, "ammonia")
        all_results.update({f"amm_int_{k}": v for k, v in amm_int_results.items()})
    except Exception as e:
        print(f"  ❌ Error loading ammonia_intensity_projections.csv: {e}")
        all_results['amm_int_load'] = False
    
    # 5. Validate steel_volumes.csv
    print("\n5️⃣  STEEL VOLUMES VALIDATION")
    print("-" * 80)
    try:
        df_steel_vol = pd.read_csv(EXPECTED_FILES["steel_volumes.csv"])
        steel_vol_results = validate_volumes(df_steel_vol, "steel")
        all_results.update({f"steel_vol_{k}": v for k, v in steel_vol_results.items()})
    except Exception as e:
        print(f"  ❌ Error loading steel_volumes.csv: {e}")
        all_results['steel_vol_load'] = False
    
    # 6. Validate ammonia_volumes.csv
    print("\n6️⃣  AMMONIA VOLUMES VALIDATION")
    print("-" * 80)
    try:
        df_amm_vol = pd.read_csv(EXPECTED_FILES["ammonia_volumes.csv"])
        amm_vol_results = validate_volumes(df_amm_vol, "ammonia")
        all_results.update({f"amm_vol_{k}": v for k, v in amm_vol_results.items()})
    except Exception as e:
        print(f"  ❌ Error loading ammonia_volumes.csv: {e}")
        all_results['amm_vol_load'] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for v in all_results.values() if v)
    total = len(all_results)
    
    if passed == total:
        print(f"✅ ALL CHECKS PASSED ({passed}/{total})")
        print("\n🎉 Industry config is valid and ready to use!")
        return 0
    else:
        failed = total - passed
        print(f"⚠️  {failed} CHECKS FAILED ({passed}/{total} passed)")
        print("\nFailed checks:")
        for check, result in all_results.items():
            if not result:
                print(f"  ❌ {check}")
        return 1


if __name__ == "__main__":
    exit(main())
