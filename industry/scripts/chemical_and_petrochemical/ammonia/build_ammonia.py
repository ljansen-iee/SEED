# scripts/ammonia/ammonia.py

from pathlib import Path
from typing import Optional, Union, Sequence, Dict, Any
import pandas as pd
import numpy as np

_industry_root = Path(__file__).resolve().parents[3]
AMMONIA_SCENARIO_XLSX = _industry_root / "input_data" / "petrochemicals" / "ammonia_all_countries_scenarios.xlsx"
AMMONIA_SCENARIO_SHEET = "combined_wide"
AMMONIA_MWH_PER_TON = 5.166
BASE_YEAR = 2020
unsd_path = _industry_root / "input_data" / "country_specific"

_AMMONIA_FILENAME_STEM = "ammonia_all_countries_scenarios"

# ---------------------------------------------------------------------------
# File + sheet detection
# ---------------------------------------------------------------------------

def _find_ammonia_file(start_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Locate ammonia_all_countries_scenarios.xlsx or .csv under likely roots.
    """
    candidates = [f"{_AMMONIA_FILENAME_STEM}.xlsx", f"{_AMMONIA_FILENAME_STEM}.csv"]

    roots: list[Path] = []
    if start_dir:
        roots.append(Path(start_dir))
    here = Path(__file__).resolve().parent
    roots += [here, *here.parents]
    roots.append(Path.cwd())

    subdirs = ("", "input_data", "input_data/petrochemicals")
    checked = []
    for r in roots:
        for sd in subdirs:
            d = (r / sd) if sd else r
            try:
                d = d.resolve()
            except Exception:
                continue
            if not d.exists():
                continue
            checked.append(d)
            for cand in candidates:
                p = d / cand
                if p.is_file():
                    return p

    raise FileNotFoundError(
        f"Could not find {_AMMONIA_FILENAME_STEM}.xlsx or .csv under searched directories: "
        + ", ".join(str(p) for p in checked[:20])
    )

# ---------------------------------------------------------------------------
# Generic helper for fuzzy column matching
# ---------------------------------------------------------------------------

def _find_col(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    """
    Return the first column name in df that loosely matches any of the candidates
    (case-insensitive, ignores spaces and % and symbols).
    """
    norm_map: Dict[str, str] = {}
    for c in df.columns:
        key = "".join(ch for ch in str(c).lower() if ch.isalnum())
        norm_map[key] = c

    for cand in candidates:
        key = "".join(ch for ch in cand.lower() if ch.isalnum())
        if key in norm_map:
            return norm_map[key]
    return None

# ---------------------------------------------------------------------------
# Main loader: ALWAYS tons if possible
# ---------------------------------------------------------------------------

def ammonia_production(path: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """
    Main loader used by build_industry_config.py.

    IMPORTANT:
    - Explicitly prefers *tons* sheets (e.g. Baseline_tons, All_scenarios_tons).
    - Only falls back to non-tons sheet if there is no *_tons in the file.
    - Returns data aggregated by (country, year).
    """
    if path is None:
        p = _find_ammonia_file()
    else:
        p = Path(path)

    # --- Read the correct sheet (tons-first) ---
    if p.suffix.lower() == ".csv":
        df_raw = pd.read_csv(p, header=0)
    else:
        xls = pd.ExcelFile(p)
        sheet_names = xls.sheet_names

        # 1) Prefer sheets whose name contains 'ton'
        tons_sheets = [s for s in sheet_names if "ton" in s.lower()]
        chosen_sheet: Optional[str] = None

        # Prefer something like 'all' + 'tons' if it exists (aggregated sheet)
        for s in tons_sheets:
            sl = s.lower()
            if "all" in sl and "ton" in sl:
                chosen_sheet = s
                break

        # Otherwise, just take the first tons sheet (e.g. Baseline_tons)
        if chosen_sheet is None and tons_sheets:
            chosen_sheet = tons_sheets[0]

        # If no tons sheet exists at all, fall back to first sheet (last resort)
        if chosen_sheet is None:
            chosen_sheet = sheet_names[0]

        df_raw = pd.read_excel(xls, sheet_name=chosen_sheet, header=0)

    # ---- Standardise core columns (country, year, productions, shares) ----
    country_col = _find_col(df_raw, "country")
    year_col    = _find_col(df_raw, "year")
    lp_col      = _find_col(df_raw, "local_production")
    nlp_col     = _find_col(df_raw, "new_local_production")
    tot_col     = _find_col(df_raw, "total_production")
    smr_col     = _find_col(df_raw, "Share of SMR + Haber-Bosch", "Share of SMR + Haber-Bosch (%)")
    renew_col   = _find_col(df_raw, "Share of renewable ammonia synthesis", "Share of renewable ammonia synthesis (%)")

    missing = []
    for logical_name, col in [
        ("country", country_col),
        ("year", year_col),
        ("local_production", lp_col),
        ("new_local_production", nlp_col),
        ("total_production", tot_col),
        ("Share of SMR + Haber-Bosch", smr_col),
        ("Share of renewable ammonia synthesis", renew_col),
    ]:
        if col is None:
            missing.append(logical_name)
    if missing:
        raise KeyError(f"Ammonia tons sheet is missing required logical columns: {', '.join(missing)}")

    df = df_raw[[country_col, year_col, lp_col, nlp_col, tot_col, smr_col, renew_col]].copy()

    df = df.rename(
        columns={
            country_col: "country",
            year_col: "year",
            lp_col: "local_production",
            nlp_col: "new_local_production",
            tot_col: "total_production",
            smr_col: "share_smrhb",
            renew_col: "share_renew",
        }
    )

    # numeric
    for c in ["year", "local_production", "new_local_production", "total_production", "share_smrhb", "share_renew"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # aggregate by country, year (in case multiple rows)
    def _agg_first_nonnull_or_mean(series: pd.Series):
        nonnull = series.dropna()
        if nonnull.empty:
            return np.nan
        first = nonnull.iloc[0]
        if len(nonnull) == 1:
            return float(first)
        try:
            uniq = pd.unique(nonnull.values)
            if len(uniq) == 1:
                return float(uniq[0])
            return float(nonnull.mean())
        except Exception:
            return float(first)

    agg_funcs = {
        "local_production": _agg_first_nonnull_or_mean,
        "new_local_production": _agg_first_nonnull_or_mean,
        "total_production": _agg_first_nonnull_or_mean,
        "share_smrhb": _agg_first_nonnull_or_mean,
        "share_renew": _agg_first_nonnull_or_mean,
    }

    grouped = df.groupby(["country", "year"], sort=False)
    rows = []
    for (country, year), grp in grouped:
        row = {"country": country, "year": int(year) if not pd.isna(year) else pd.NA}
        for col, func in agg_funcs.items():
            row[col] = func(grp[col])
        rows.append(row)

    df_out = pd.DataFrame(rows)
    df_out["production"] = pd.to_numeric(df_out["total_production"], errors="coerce")
    df_out["year"] = pd.to_numeric(df_out["year"], errors="coerce").astype("Int64")

    for c in ["local_production", "new_local_production", "total_production", "production", "share_smrhb", "share_renew"]:
        df_out[c] = pd.to_numeric(df_out[c], errors="coerce")

    cols_out = [
        "country",
        "year",
        "local_production",
        "new_local_production",
        "total_production",
        "production",
        "share_smrhb",
        "share_renew",
    ]
    df_out = df_out[cols_out]
    df_out = df_out.sort_values(["country", "year"]).reset_index(drop=True)
    return df_out

# ---------------------------------------------------------------------------
# HVC series builder (unchanged)
# ---------------------------------------------------------------------------

def build_hvc_production_series(
    base_2020: float,
    target_years: list[int],
    scenarios: list[str],
    cagr_cfg: dict,
    y0: int = 2020,
    y_split: int = 2030,
    y_end_anchor: int = 2050,
) -> dict:
    def _nearest_rate(year_anchor: int, sc: str) -> float:
        if year_anchor in cagr_cfg:
            v = cagr_cfg[year_anchor]
            if isinstance(v, dict):
                return float(v.get(sc, 0.0))
            idx = scenarios.index(sc)
            return float(v[idx])
        if not cagr_cfg:
            return 0.0
        years = sorted(int(k) for k in cagr_cfg.keys())
        nearest = min(years, key=lambda k: abs(k - year_anchor))
        v = cagr_cfg[nearest]
        if isinstance(v, dict):
            return float(v.get(sc, 0.0))
        idx = scenarios.index(sc)
        return float(v[idx])

    values_at_split: Dict[str, float] = {}
    for sc in scenarios:
        r_2030 = _nearest_rate(y_split, sc)
        values_at_split[sc] = base_2020 * ((1.0 + r_2030) ** (y_split - y0))

    out: Dict[int, Any] = {y0: float(base_2020)}
    for y in sorted(set(target_years)):
        out.setdefault(y, {})
        for sc in scenarios:
            if y <= y_split:
                r_2030 = _nearest_rate(y_split, sc)
                val = base_2020 * ((1.0 + r_2030) ** (y - y0))
            else:
                r_2050 = _nearest_rate(y_end_anchor, sc)
                val = values_at_split[sc] * ((1.0 + r_2050) ** (y - y_split))
            out[y][sc] = float(val)
    return out

# ---------------------------------------------------------------------------
# Helpers for scenario-specific extraction (tons-first)
# ---------------------------------------------------------------------------

def _nearest_prev_value(df_country_scenario: pd.DataFrame, year: int, col: str) -> float | None:
    if df_country_scenario.empty or col not in df_country_scenario.columns:
        return None
    le = df_country_scenario[df_country_scenario["year"] <= year]
    if not le.empty:
        return float(le.loc[le["year"].idxmax(), col])
    idx = (df_country_scenario["year"] - year).abs().idxmin()
    return float(df_country_scenario.loc[idx, col])

def _interp_total_production(df_country_scenario: pd.DataFrame, target_year: int) -> float | None:
    if df_country_scenario.empty or "total_production" not in df_country_scenario.columns:
        return None
    sub = df_country_scenario.dropna(subset=["year", "total_production"]).copy()
    if sub.empty:
        return None
    sub = sub.sort_values("year")
    years = sub["year"].astype(int).to_numpy()
    vals = sub["total_production"].astype(float).to_numpy()
    match = sub[sub["year"] == target_year]
    if not match.empty:
        return float(match["total_production"].iloc[0])
    if len(years) == 1:
        return float(vals[0])
    return float(np.interp(target_year, years, vals))

def _build_scenario_frames_tons_first(
    xls: pd.ExcelFile,
    scenarios: Sequence[str],
) -> Dict[str, pd.DataFrame]:
    """
    Build dict: scenario_label (from main.py) -> DataFrame for that scenario.

    Maps scenarios by POSITION (no hardcoded keywords):
      - scenarios[0] -> first tons sheet
      - scenarios[1] -> second tons sheet
      - scenarios[2] -> third tons sheet
      
    If no tons sheets exist, falls back to the first sheet.
    """
    sheet_names = xls.sheet_names
    tons_sheets = [s for s in sheet_names if "tons" in s.lower()]

    scenario_frames: Dict[str, pd.DataFrame] = {}

    if tons_sheets:
        # Use sheets IN THEIR ACTUAL ORDER (no sorting by keywords)
        for idx, sc_label in enumerate(scenarios):
            sheet_idx = min(idx, len(tons_sheets) - 1)
            sheet_name = tons_sheets[sheet_idx]
            df_sc = pd.read_excel(xls, sheet_name=sheet_name)

            country_col = _find_col(df_sc, "country")
            year_col    = _find_col(df_sc, "year")
            lp_col      = _find_col(df_sc, "local_production")
            tot_col     = _find_col(df_sc, "total_production")

            cols = [c for c in [country_col, year_col, lp_col, tot_col] if c is not None]
            df_sc = df_sc[cols].copy()

            df_sc = df_sc.rename(
                columns={
                    country_col: "country",
                    year_col: "year",
                    lp_col: "local_production",
                    tot_col: "total_production",
                }
            )
            if "year" in df_sc.columns:
                df_sc["year"] = pd.to_numeric(df_sc["year"], errors="coerce").astype("Int64")
            for c in ("local_production", "total_production"):
                if c in df_sc.columns:
                    df_sc[c] = pd.to_numeric(df_sc[c], errors="coerce")

            scenario_frames[sc_label] = df_sc
        return scenario_frames

    # Fallback: no tons sheets -> read first sheet and share across scenarios
    df_raw = pd.read_excel(xls, sheet_name=sheet_names[0])
    country_col = _find_col(df_raw, "country")
    year_col    = _find_col(df_raw, "year")
    lp_col      = _find_col(df_raw, "local_production")
    tot_col     = _find_col(df_raw, "total_production")
    cols = [c for c in [country_col, year_col, lp_col, tot_col] if c is not None]
    df_raw = df_raw[cols].copy()
    df_raw = df_raw.rename(
        columns={
            country_col: "country",
            year_col: "year",
            lp_col: "local_production",
            tot_col: "total_production",
        }
    )
    if "year" in df_raw.columns:
        df_raw["year"] = pd.to_numeric(df_raw["year"], errors="coerce").astype("Int64")
    for c in ("local_production", "total_production"):
        if c in df_raw.columns:
            df_raw[c] = pd.to_numeric(df_raw[c], errors="coerce")

    for sc_label in scenarios:
        scenario_frames[sc_label] = df_raw.copy()

    return scenario_frames

# ---------------------------------------------------------------------------
# Scenario-specific extraction
# ---------------------------------------------------------------------------

def extract_ammonia_values_for_country(
    df_ammonia: pd.DataFrame,
    scenario_frames: Dict[str, pd.DataFrame],
    country: str,
    base_year: int,
    target_years: Sequence[int],
    scenarios: Sequence[str],
) -> pd.DataFrame:
    """
    For each scenario in `scenarios`:
      - base_year row: nearest previous local_production (from *_tons sheet)
      - target years: interpolated total_production (from *_tons sheet)
    """
    rows: list[Dict[str, Any]] = []

    for sc_label in scenarios:
        df_sc = scenario_frames.get(sc_label)
        if df_sc is None or df_sc.empty:
            sub = df_ammonia[df_ammonia["country"].astype(str).str.strip() == str(country).strip()].copy()
        else:
            sub = df_sc[df_sc["country"].astype(str).str.strip() == str(country).strip()].copy()

        if "year" in sub.columns:
            sub["year"] = pd.to_numeric(sub["year"], errors="coerce")

        base_val = _nearest_prev_value(sub, base_year, "local_production") if "local_production" in sub.columns else None
        rows.append(
            {
                "country": country,
                "scenario_label": sc_label,
                "year": base_year,
                "value_type": "local_production",
                "value": base_val,
                "note": f"nearest prev year <= {base_year} or nearest available",
            }
        )

        for ty in target_years:
            val = _interp_total_production(sub, ty) if "total_production" in sub.columns else None
            rows.append(
                {
                    "country": country,
                    "scenario_label": sc_label,
                    "year": ty,
                    "value_type": "total_production",
                    "value": val,
                    "note": "interpolated if exact year missing",
                }
            )

    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# Public helper for main.py
# ---------------------------------------------------------------------------

def extract_for_countries_from_loader(
    path: str | None = None,
    countries: Sequence[str] | None = None,
    base_year: int = 2020,
    target_years: Sequence[int] = (2030, 2050),
    scenarios: Sequence[str] = ("Baseline", "RF", "EL"),
) -> pd.DataFrame:
    """
    path optional: if None, ammonia_production() will auto-discover file.

    Uses *_tons sheets if present and maps POSITIONALLY:
      scenarios[0] -> Baseline_tons (or first tons-like sheet)
      scenarios[1] -> Ambitious Policies_tons (or second tons-like sheet)
      scenarios[2] -> Net Zero_tons (or third tons-like sheet)
    """
    df_loaded = ammonia_production(path) if path else ammonia_production()

    if path:
        p = Path(path)
    else:
        p = _find_ammonia_file()
    xls = pd.ExcelFile(p)

    scenario_frames = _build_scenario_frames_tons_first(xls, scenarios)

    if countries is None:
        countries = df_loaded["country"].dropna().unique().tolist()

    out_frames = []
    for c in countries:
        out_frames.append(
            extract_ammonia_values_for_country(
                df_loaded,
                scenario_frames,
                c,
                base_year,
                target_years,
                scenarios,
            )
        )

    return pd.concat(out_frames, ignore_index=True)
