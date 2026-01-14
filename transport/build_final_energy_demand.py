# build_final_energy_demand.py
import os
import glob
import pandas as pd
from build_transport_calc import calc_for_scenario
from build_transport_indicators import generate_transport_indicators

# Get the absolute path of this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSPORT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output_data")
# Base results folder
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# Choose here add list of countries 
#[ "Algeria","Argentina","Brazil","Chile","Colombia","Egypt","Libya","Mexico",
#  "Namibia","Peru","Tunisia","Uruguay","Morocco","South Africa",
#  "Angola","Benin","Botswana","Burkina Faso","Burundi","Cameroon",
#  "Central African Republic","Chad","Comoros","Djibouti","Equatorial Guinea","Eritrea",
#  "Ethiopia","Gabon","Gambia","Ghana","Guinea","Guinea Bissau","Kenya","Lesotho",
#  "Liberia","Madagascar","Malawi","Mali","Mauritania","Mozambique","Namibia","Niger",
#  "Rwanda","Senegal","Sierra Leone","Somalia","Sudan","Tanzania","Togo","Uganda",
#  "Zambia","Zimbabwe","Seychelles","Cote D'Ivoire","Sao Tome and Principe",
#  "South Sudan","Cabo Verde", "Congo", "Eswatini" ] 

COUNTRY = [ "Algeria","Argentina","Brazil","Chile","Colombia","Egypt","Libya","Mexico",
                             "Namibia","Peru","Tunisia","Uruguay","Morocco","South Africa",
                            "Angola","Benin","Botswana","Burkina Faso","Burundi","Cameroon",
                             "Central African Republic","Chad","Comoros","Djibouti","Equatorial Guinea","Eritrea",
                             "Ethiopia","Gabon","Gambia","Ghana","Guinea","Guinea Bissau","Kenya","Lesotho",
                             "Liberia","Madagascar","Malawi","Mali","Mauritania","Mozambique","Namibia","Niger",
                             "Rwanda","Senegal","Sierra Leone","Somalia","Sudan","Tanzania","Togo","Uganda",
                             "Zambia","Zimbabwe","Seychelles","Cote D'Ivoire","Sao Tome and Principe",
                             "South Sudan","Cabo Verde", "Congo", "Eswatini" ] 


def find_latest_dir(base_dir="output_data") -> str:
    dirs = [d for d in glob.glob(os.path.join(base_dir, "DKS_*")) if os.path.isdir(d)]
    if not dirs:
        raise FileNotFoundError(f"No DKS_* folders found in {base_dir}")
    return max(dirs, key=os.path.getmtime)

def list_countries(latest_dir: str):
    files = glob.glob(os.path.join(latest_dir, "output_*.xlsx"))
    return sorted([os.path.splitext(os.path.basename(f))[0].replace("output_", "") for f in files])

def find_country_file(country: str, latest_dir: str) -> str:
    path = os.path.join(latest_dir, f"output_{country}.xlsx")
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    return path

def load_country_dataframe(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df["Metric"] = df["Metric"].astype(str).str.replace("\xa0", " ").str.strip()
    # numeric columns only
    numeric_cols = [c for c in df.columns if c not in ["Metric", "Units"]]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # drop duplicates on Metric
    df = df.drop_duplicates(subset=["Metric"], keep="first")
    return df

def dataframe_to_metrics_raw(df: pd.DataFrame) -> dict:
    return df.set_index("Metric").to_dict(orient="index")

def build_summary(df, metrics_raw):
    """
    Build summaries by Fuel/Mode/Subsector/End-Use.
    - Drops any blank 'Fuel' totals coming from detail DF
    - Renames *_EL to *_AT
    - Applies biofuel blending for Gasoline/Diesel/Kerosene into Bio Ethanol/Bio Diesel/Bio Kerosene
    - Reorders columns and rows and adds Sum
    """
    # 0) Remove rows that have an empty Fuel label (e.g., manual TOTAL rows)
    df = df[df["Fuel"].astype(str).str.strip() != ""]

    # 1) Base summaries
    fuel_summary = (
        df.groupby(["Fuel", "Scenario"])["Final Energy Demand (GWh)"]
          .sum()
          .unstack(fill_value=0)
    )
    mode_summary = (
        df.groupby(["Mode", "Scenario"])["Final Energy Demand (GWh)"]
          .sum()
          .unstack(fill_value=0)
    )
    subsector_summary = (
        df.groupby(["Subsector", "Scenario"])["Final Energy Demand (GWh)"]
          .sum()
          .unstack(fill_value=0)
    )
    enduse_summary = (
        df.groupby(["End-Use", "Scenario"])["Final Energy Demand (GWh)"]
          .sum()
          .unstack(fill_value=0)
    )

    # 2) Rename columns (_EL -> _AT)
    def rename_cols(wide_df):
        wide_df.columns = [c.replace("_EL", "_AT") for c in wide_df.columns]
        return wide_df

    fuel_summary = rename_cols(fuel_summary)
    mode_summary = rename_cols(mode_summary)
    subsector_summary = rename_cols(subsector_summary)
    enduse_summary = rename_cols(enduse_summary)

    # 3) Apply biofuel blending on the FUEL summary ONLY (doesn't touch the detailed rows)
    def share(metric_name, scn):
        """
        Return blend share as a FRACTION (0..1).
        Works whether Excel has 2 (=> 2%) or 0.02.
        Also falls back 2030_AT → 2030_EL if needed.
        """
        d = metrics_raw.get(metric_name, {})

        # scenario fallback: AT columns may be called EL in inputs
        scn_key = scn if scn in d else scn.replace("_AT", "_EL")

        try:
            val = float(d.get(scn_key, 0.0) or 0.0)
        except Exception:
            val = 0.0

        # If it's >1, it’s a percent number; convert to fraction
        return val / 100.0 if val > 1 else val

    # ensure Bio rows and LPG exist
    for idx in ["Bio Ethanol", "Bio Diesel", "Bio Kerosene", "LPG"]:
        if idx not in fuel_summary.index:
            fuel_summary.loc[idx] = 0.0

    for scn in list(fuel_summary.columns):
        be = share("Share of Bioethanol in Road Gasoline", scn)
        bd = share("Share of Biodiesel in Road Diesel", scn)
        bk = share("Share of Biokerosene in Internal Aviation Fuel", scn)

        gas = fuel_summary.at["Gasoline", scn] if "Gasoline" in fuel_summary.index else 0.0
        die = fuel_summary.at["Diesel", scn]   if "Diesel" in fuel_summary.index   else 0.0
        ker = fuel_summary.at["Kerosene", scn] if "Kerosene" in fuel_summary.index else 0.0

        gas_bio = gas * be
        die_bio = die * bd
        ker_bio = ker * bk

        fuel_summary.at["Bio Ethanol", scn]  = gas_bio
        fuel_summary.at["Bio Diesel", scn]   = die_bio
        fuel_summary.at["Bio Kerosene", scn] = ker_bio

        # reduce fossil parts accordingly (and prevent negatives)
        if "Gasoline" in fuel_summary.index:
            fuel_summary.at["Gasoline", scn] = max(0.0, gas - gas_bio)
        if "Diesel" in fuel_summary.index:
            fuel_summary.at["Diesel", scn]   = max(0.0, die - die_bio)
        if "Kerosene" in fuel_summary.index:
            fuel_summary.at["Kerosene", scn] = max(0.0, ker - ker_bio)


    # 4) Keep only the columns you want and order them
    def scenario_sort_key(s):
        digits = "".join(filter(str.isdigit, s))
        return int(digits) if digits else 9999

    fuel_summary = fuel_summary[
        sorted(fuel_summary.columns, key=scenario_sort_key)
    ]


    # 5) Order rows like your reference
    fuels_order = [
        "Ammonia",
        "Bio Diesel", "Bio Ethanol", "Bio Kerosene",
        "Diesel", "Electricity", "Gasoline", "Hydrogen", "Kerosene", "LPG",
        "Methanol"
    ]
    fuel_summary = fuel_summary.reindex([f for f in fuels_order if f in fuel_summary.index])

    # 6) Add Sum row and round
    fuel_summary.loc["Sum"] = fuel_summary.sum(numeric_only=True, axis=0)
    fuel_summary = fuel_summary.round(2)

    return fuel_summary, mode_summary, subsector_summary, enduse_summary



def run(country: str, base_dir: str = "output_data") -> None:
    latest_dir = find_latest_dir(base_dir)
    print(f" Latest folder: {latest_dir}")
    print(f"DEBUG: base_dir = {base_dir}")
    available = list_countries(latest_dir)
    if country not in available:
        raise ValueError(f"{country} not found in latest folder. Available: {', '.join(available)}")

    file_path = find_country_file(country, latest_dir)
    print(f" Using file: {file_path}")

    df = load_country_dataframe(file_path)
    # --- Standardize scenario names (_EL → _AT) ---
    metrics_raw = dataframe_to_metrics_raw(df)

    # Available scenarios
    scenarios = [c for c in df.columns if c not in ["Metric", "Units"]]

    all_results = []
    for scn in scenarios:
        df_scn = calc_for_scenario(metrics_raw, scn)

        if df_scn is None or df_scn.empty:
            print(f"  No data generated for scenario {scn}, skipping")
            continue

        all_results.append(df_scn)

    if not all_results:
        raise ValueError(f"No valid scenarios produced for {country}")

    final_df = pd.concat(all_results, ignore_index=True)

    # --- NEW: Build summaries ---
    fuel_summary, mode_summary, subsector_summary, enduse_summary = build_summary(final_df, metrics_raw)

    # Make a subfolder for the country
    country_results_dir = os.path.join(RESULTS_DIR, country)
    os.makedirs(country_results_dir, exist_ok=True)

    # Save detailed results
    out_file = os.path.join(country_results_dir, "final_energy_demand.xlsx")
    final_df.to_excel(out_file, index=False)
    print(f" Saved detailed results: {out_file}")

    indicators_df = generate_transport_indicators(final_df, country)
    indicators_file = os.path.join(country_results_dir, "transport_indicators.xlsx")
    indicators_df.to_excel(indicators_file, index=False)
    print(f" Saved indicators: {indicators_file}")

    # Save summaries in one Excel with multiple sheets
    summary_file = os.path.join(country_results_dir, "summary.xlsx")
    with pd.ExcelWriter(summary_file) as writer:
        fuel_summary.to_excel(writer, sheet_name="Fuel")
        mode_summary.to_excel(writer, sheet_name="Mode")
        subsector_summary.to_excel(writer, sheet_name="Subsector")
        enduse_summary.to_excel(writer, sheet_name="EndUse")

    print(f" Saved summaries: {summary_file}")


if __name__ == "__main__":
    for country in COUNTRY:
        try:
            print(f"\n{'='*50}\n Processing country: {country}\n{'='*50}")
            run(country=country, base_dir=TRANSPORT_OUTPUT_DIR)
        except Exception as e:
            print(f" Error processing {country}: {e}")

