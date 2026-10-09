"""Validated annual country exports; importing performs no I/O.

See docs/data/pypsa-output-contract.md. Industry preserves the example's
country/carrier rows and 13 subsectors. No EL/RF scenario equivalence is implied.
"""
import argparse
import csv
import json
from itertools import product
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import pycountry

SCENARIOS = ("BAU", "Progressive", "Optimistic")
TARGET_YEARS = (2030, 2035, 2040, 2045, 2050)
KEYS = ["country", "scenario", "year"]
ENERGY_COLUMNS = (
    "agriculture biomass", "agriculture coal", "agriculture electricity", "agriculture oil",
    "district heat share", "electricity services space", "electricity services water",
    "non energy biomass", "non energy electricity", "non energy gas", "non energy heat",
    "non energy oil", "services biomass", "services electricity", "services gas", "services oil",
    "total services space", "total services water", "electricity residential space",
    "electricity residential water", "electricity residential", "residential hydrogen",
    "residential coal", "residential biomass", "residential gas", "residential oil",
    "residential heat biomass", "residential heat gas", "residential heat oil",
    "residential heat biomass no cooking", "residential heat gas no cooking",
    "residential heat oil no cooking", "total residential space", "total residential water",
    "electricity rail", "total rail", "road biomass", "road electricity", "road gas", "road oil",
    "total road", "total road ev", "total road fcev", "total road ice", "total domestic aviation",
    "total domestic navigation", "total navigation hydrogen", "total navigation oil",
    "total international aviation", "total international navigation", "international aviation e-fuel",
    "other biomass", "other electricity", "other gas", "other heat", "other oil",
    "total navigation ammonia", "total rail hydrogen", "international navigation e-fuel",
)
INDUSTRY_CARRIERS = (
    "oil", "gas", "electricity", "coal", "biomass", "hydrogen", "ammonia",
    "steel", "methanol", "process emissions", "low-temperature heat",
)
INDUSTRY_SECTORS = (
    "chemical and petrochemical", "construction", "food and tobacco", "iron and steel",
    "machinery", "mining and quarrying", "non-ferrous metals", "non-metallic minerals",
    "other", "paper pulp and print", "textile and leather", "transport equipment",
    "wood and wood products",
)
INDUSTRY_COLUMNS = INDUSTRY_SECTORS
INDUSTRY_UNITS = {
    col: "tSteel/a" if col == "steel" else "tCO2/a" if col == "process emissions" else "MWh/a"
    for col in INDUSTRY_CARRIERS
}
INDUSTRY_QUANTITY_CLASSES = {
    col: "product_activity" if col == "steel" else "process_emissions" if col == "process emissions" else "energy"
    for col in INDUSTRY_CARRIERS
}
# Verified FinalEnergyCalculator contract: its energy_MWh field contains tonnes
# for steel, MWh for every other quantity (including ammonia's LHV conversion).
CALCULATOR_UNITS = {col: unit for col, unit in INDUSTRY_UNITS.items() if col != "process emissions"}
RESIDENTIAL_MAPPING = {
    "electricity residential space": "electricity residential space",
    "electricity residential water": "electricity residential water",
    "electricity residential": "electricity residential",
    "residential hydrogen with cooking": "residential hydrogen",
    "total residential space": "total residential space",
    "total residential water": "total residential water",
}
for _fuel in ("biomass", "gas", "oil"):
    RESIDENTIAL_MAPPING[f"residential heat {_fuel} with cooking"] = f"residential {_fuel}"
    RESIDENTIAL_MAPPING[f"residential heat {_fuel}"] = f"residential heat {_fuel} no cooking"
ADDITIONAL_FILES = {
    "agriculture": "agriculture_fuel_demand_history_future.csv",
    "services": "services_fuel_demand_history_future.csv",
    "non energy": "non_energy_fuel_demand_history_future.csv",
    "other": "other_fuel_demand_history_future.csv",
}
TRANSPORT_COLUMNS = tuple(
    col for col in ENERGY_COLUMNS
    if col.startswith(("road ", "total road", "total rail", "total navigation", "total domestic",
                       "total international", "international aviation", "international navigation"))
    or col == "electricity rail"
)
TRANSPORT_REQUIRED = tuple(col for col in TRANSPORT_COLUMNS if "e-fuel" not in col)
TRANSPORT_DIAGNOSTICS = {
    "total navigation biomass": "total domestic navigation",
    "total aviation biomass": "total domestic aviation",
}
CARRIER_ALIASES = {"solid biomass": "biomass", "heat": "low-temperature heat"}
COUNTRY_ALIASES = {"South Korea": "KR", "Russia": "RU", "Vietnam": "VN"}


def get_iso_code(country_name: str) -> str:
    """Resolve exact names/codes or documented aliases, never invent XX."""
    if not isinstance(country_name, str) or not country_name.strip():
        raise ValueError(f"Missing country identifier: {country_name!r}")
    name = country_name.strip()
    try:
        return pycountry.countries.lookup(COUNTRY_ALIASES.get(name, name)).alpha_2
    except LookupError as exc:
        raise ValueError(f"Unknown country: {name!r}") from exc


def _required(frame, columns, label):
    if not frame.columns.is_unique:
        raise ValueError(f"{label}: duplicate column names")
    missing = set(columns).difference(frame.columns)
    if missing:
        raise ValueError(f"{label}: missing columns {sorted(missing)}")


def _unique(frame, keys, label):
    _required(frame, keys, label)
    for key in keys:
        if frame[key].isna().any() or frame[key].astype(str).str.strip().eq("").any():
            raise ValueError(f"{label}: missing identifier {key}")
    duplicates = frame.duplicated(list(keys), keep=False)
    if duplicates.any():
        raise ValueError(f"{label}: duplicate keys {frame.loc[duplicates, list(keys)].head().to_dict('records')}")


def _values(frame, columns, label):
    out = frame.copy()
    _required(out, columns, label)
    for col in columns:
        out[col] = pd.to_numeric(out[col], errors="raise")
        if not np.isfinite(out[col].to_numpy(dtype=float)).all() or (out[col] < 0).any():
            raise ValueError(f"{label}: {col} must be finite and nonnegative")
    return out


def _dimensions(frame, label, *, scenario=True):
    _required(frame, KEYS if scenario else ["country", "year"], label)
    out = frame.copy()
    out["country"] = out["country"].map(get_iso_code)
    year = pd.to_numeric(out["year"], errors="raise")
    if not np.isfinite(year.to_numpy(dtype=float)).all() or (year % 1 != 0).any():
        raise ValueError(f"{label}: year must be a finite integer")
    out["year"] = year.astype(int)
    if scenario and (out["scenario"].isna().any() or not out["scenario"].isin(SCENARIOS).all()):
        raise ValueError(f"{label}: scenario must be one of {SCENARIOS}")
    return out


def _scope(countries, years, scenarios):
    countries, years, scenarios = tuple(map(get_iso_code, countries)), tuple(years), tuple(scenarios)
    if not countries or not years or not scenarios:
        raise ValueError("countries, years and scenarios must be nonempty")
    if any(len(set(items)) != len(items) for items in (countries, years, scenarios)):
        raise ValueError("Duplicate requested countries, years or scenarios")
    if not set(years).issubset(TARGET_YEARS) or not set(scenarios).issubset(SCENARIOS):
        raise ValueError("Unsupported requested year or scenario")
    return countries, years, scenarios


def _coverage(frame, countries, years, scenarios, label):
    actual = set(frame[KEYS].drop_duplicates().itertuples(index=False, name=None))
    expected = set(product(countries, scenarios, years))
    if actual != expected:
        raise ValueError(f"{label}: coverage mismatch; missing={sorted(expected - actual)[:8]}, "
                         f"unexpected={sorted(actual - expected)[:8]}")


def _select(frame, countries, years, scenarios=None):
    mask = frame["country"].isin(countries) & frame["year"].isin(years)
    if scenarios is not None:
        mask &= frame["scenario"].isin(scenarios)
    return frame.loc[mask].copy()


def _unmapped(frame, known, label):
    extras = [col for col in frame.columns if col not in known]
    checked = _values(frame, extras, label)
    nonzero = [col for col in extras if checked[col].ne(0).any()]
    if nonzero:
        raise ValueError(f"{label}: nonzero unmapped columns {nonzero}; explicit schema decision required")
    return extras


def _read_csv(path):
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        header = next(csv.reader(stream))
    if len(set(header)) != len(header):
        raise ValueError(f"{path}: duplicate CSV header")
    # ISO2 Namibia is literally "NA", not a missing country. Keep identifiers
    # intact while still treating genuinely empty numeric fields as missing.
    return pd.read_csv(path, keep_default_na=False, na_values=["", "NaN", "nan"])


def _residential_contract(frame):
    """Validate overlapping summaries; never count a heat subset twice."""
    mapping = dict(RESIDENTIAL_MAPPING)
    # The corrected producer separates coal from biomass. Legacy summaries have
    # no coal field: never infer or subtract coal from an ambiguous biomass sum.
    if "residential coal with cooking" in frame:
        mapping["residential coal with cooking"] = "residential coal"
    elif "residential coal" in frame:
        mapping["residential coal"] = "residential coal"
    checked = _values(frame, list(mapping), "residential")
    diagnostics = {}
    for fuel in ("hydrogen", "coal"):
        full, duplicate = f"residential {fuel} with cooking", f"residential {fuel}"
        if full in checked and duplicate in checked:
            checked = _values(checked, [duplicate], "residential")
            if not np.allclose(checked[full], checked[duplicate], rtol=1e-10, atol=1e-8):
                raise ValueError(f"residential: {fuel} summaries disagree")
            diagnostics[duplicate] = {"included_in": mapping[full], "validation": f"equals {full}"}
    for fuel in ("biomass", "gas", "oil"):
        subset, full = f"residential heat {fuel}", f"residential heat {fuel} with cooking"
        if (checked[subset] > checked[full] + 1e-8).any():
            raise ValueError(f"residential: {subset} exceeds full carrier demand {full}")
    electricity_parts = checked["electricity residential space"] + checked["electricity residential water"]
    if (electricity_parts > checked["electricity residential"] + 1e-8).any():
        raise ValueError("residential: space + water electricity exceeds total electricity")
    for end_use in ("space", "water"):
        if (checked[f"electricity residential {end_use}"] > checked[f"total residential {end_use}"] + 1e-8).any():
            raise ValueError(f"residential: electricity exceeds total {end_use}")
    non_cooking = sum(checked[f"residential heat {fuel}"] for fuel in ("biomass", "gas", "oil"))
    # No separate coal/hydrogen non-cooking split is published; full demand is
    # only an upper bound here, not an invented end-use allocation.
    for source, target in mapping.items():
        if target in ("residential coal", "residential hydrogen"):
            non_cooking = non_cooking + checked[source]
    heat_parts = checked["total residential space"] + checked["total residential water"] - electricity_parts
    if (heat_parts > non_cooking + 1e-8).any():
        raise ValueError("residential: space + water fuel demand exceeds non-cooking carrier bound")
    return checked, mapping, diagnostics


def _transport_contract(frame, factor):
    """Biomass is a diagnostic subset, not missing energy or extra oil."""
    present = [col for col in TRANSPORT_DIAGNOSTICS if col in frame]
    checked = _values(frame, present, "transport")
    diagnostics = {}
    for col in present:
        total = TRANSPORT_DIAGNOSTICS[col]
        if (checked[col] > checked[total] + 1e-8).any():
            raise ValueError(f"transport: {col} exceeds {total}")
        records = checked[KEYS + [col]].rename(columns={col: "value"}).copy()
        records["value"] *= factor
        diagnostics[col] = {"included_in": total, "unit": "TWh/a", "scale": factor,
                            "validation": "nonnegative subset of domestic total; not added again",
                            "values": records.to_dict("records")}
    navigation_fuels = checked[["total navigation oil", "total navigation hydrogen",
                                "total navigation ammonia"]].sum(axis=1)
    if "total navigation biomass" in checked:
        navigation_fuels = navigation_fuels + checked["total navigation biomass"]
    residual = (checked["total domestic navigation"] - navigation_fuels) * factor
    inconsistent = ~np.isclose(residual, 0.0, rtol=0, atol=1e-8)
    if inconsistent.any():
        evidence = checked.loc[inconsistent, KEYS].assign(residual_TWh=residual[inconsistent]).to_dict("records")
        raise ValueError("BLOCKER: transport: total domestic navigation must equal oil + hydrogen + ammonia + biomass; "
                         "unrepresented navigation electricity/unknown carrier or inconsistent totals; "
                         f"no supported example-schema allocation: {evidence[:8]}")
    return checked, diagnostics


def load_residential_data(residential_output_dir: Path) -> pd.DataFrame:
    return _read_csv(Path(residential_output_dir) / "residential_all_scenarios_years_countries.csv")


def load_additional_sectors_data(additional_output_dir: Path) -> pd.DataFrame:
    merged = None
    for prefix, name in ADDITIONAL_FILES.items():
        sector = _dimensions(_read_csv(Path(additional_output_dir) / name), prefix, scenario=False)
        _required(sector, ["unit"], prefix)
        if not sector["unit"].eq("TWh").all():
            raise ValueError(f"{prefix}: declared unit must be TWh")
        _unique(sector, ["country", "year"], prefix)
        measures = [col for col in sector if col not in ("country", "year", "unit")]
        if not measures or any(not col.startswith(prefix + " ") for col in measures):
            raise ValueError(f"{prefix}: wrong or missing sector-prefixed columns")
        sector = _values(sector, measures, prefix).drop(columns="unit")
        if merged is None:
            merged = sector
        else:
            merged = merged.merge(sector, on=["country", "year"], how="outer",
                                  validate="one_to_one", indicator=True)
            if not merged["_merge"].eq("both").all():
                raise ValueError(f"{prefix}: additional-sector country/year coverage differs")
            merged = merged.drop(columns="_merge")
    merged.attrs["unit"] = "TWh"
    return merged


def load_transport_data(transport_output_dir: Path, *, years=TARGET_YEARS, scenarios=SCENARIOS,
                        unit="TWh") -> pd.DataFrame:
    """Aggregate indicators already convert detailed GWh to TWh in the current producer."""
    frames = []
    for scenario, year in product(scenarios, years):
        frame = _read_csv(Path(transport_output_dir) / f"transport_{scenario}_{year}.csv")
        _required(frame, ["scenario", "country"], "transport")
        if not frame["scenario"].eq(f"{year}_{scenario}").all():
            raise ValueError(f"Transport filename/row scenario mismatch: {scenario} {year}")
        if "year" in frame and not pd.to_numeric(frame["year"], errors="raise").eq(year).all():
            raise ValueError("Transport filename/row year mismatch")
        frame["scenario"], frame["year"] = scenario, year
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True)
    out.attrs["unit"] = unit
    return out


def _split_tables(frame, columns, years, scenarios, metadata):
    tables = {}
    for scenario, year in product(scenarios, years):
        table = frame.loc[(frame["scenario"] == scenario) & (frame["year"] == year)]
        table = _values(table.set_index("country").loc[:, list(columns)].sort_index(), columns, "output")
        table.index.name = "country"
        table.attrs["metadata"] = dict(metadata)
        tables[(scenario, year)] = table
    return tables


def build_energy_totals(residential_df: pd.DataFrame, additional_df: pd.DataFrame,
                        transport_df: pd.DataFrame, *, countries: Sequence[str],
                        years=TARGET_YEARS, scenarios=SCENARIOS, transport_unit: str | None = None):
    """Return {(scenario, year): frame} without writes; units must be declared.

    Residential summary is TWh by producer contract. Additional data declares
    TWh in a unit column or attrs['unit']; transport declares GWh or TWh.
    """
    countries, years, scenarios = _scope(countries, years, scenarios)
    residential = _dimensions(residential_df, "residential")
    additional = _dimensions(additional_df, "additional", scenario=False)
    transport = _dimensions(transport_df, "transport")
    for frame, keys, label in ((residential, KEYS, "residential"),
                               (additional, ["country", "year"], "additional"),
                               (transport, KEYS, "transport")):
        _unique(frame, keys, label)
    residential = _select(residential, countries, years, scenarios)
    additional = _select(additional, countries, years)
    transport = _select(transport, countries, years, scenarios)
    _coverage(residential, countries, years, scenarios, "residential")
    _coverage(transport, countries, years, scenarios, "transport")
    if set(additional[["country", "year"]].itertuples(index=False, name=None)) != set(product(countries, years)):
        raise ValueError("additional: missing country/year coverage")
    if "unit" in additional:
        if not additional["unit"].eq("TWh").all():
            raise ValueError("additional: declared unit must be TWh")
        additional = additional.drop(columns="unit")
    elif additional_df.attrs.get("unit") != "TWh":
        raise ValueError("additional: missing TWh unit declaration")
    residential, residential_mapping, residential_diagnostics = _residential_contract(residential)
    if "district heat share" in residential:
        residential = _values(residential, ["district heat share"], "residential")
        if (residential["district heat share"] > 1).any():
            raise ValueError("residential: district heat share must be a fraction in [0, 1]")
    transport = _values(transport, TRANSPORT_REQUIRED, "transport")
    transport_unit = transport_unit or transport_df.attrs.get("unit")
    if transport_unit not in ("GWh", "TWh"):
        raise ValueError("transport: declare GWh or TWh explicitly")
    if "unit" in transport:
        if not transport["unit"].eq(transport_unit).all():
            raise ValueError("transport: unit column contradicts declared unit")
        transport = transport.drop(columns="unit")
    if transport_df.attrs.get("unit", transport_unit) != transport_unit:
        raise ValueError("transport: conflicting unit declarations")
    factor = 0.001 if transport_unit == "GWh" else 1.0
    transport, transport_diagnostics = _transport_contract(transport, factor)
    additional_columns = [col for col in ENERGY_COLUMNS
                          if col.startswith(tuple(p + " " for p in ADDITIONAL_FILES))]
    additional = _values(additional, [col for col in additional_columns if not col.endswith(" heat")], "additional")
    omitted = {
        "residential": _unmapped(residential, KEYS + list(residential_mapping) +
                                  list(residential_diagnostics) + ["district heat share"], "residential"),
        "additional": _unmapped(additional, ["country", "year"] + additional_columns, "additional"),
        "transport": _unmapped(transport, KEYS + list(TRANSPORT_COLUMNS) + list(transport_diagnostics), "transport"),
    }
    res = residential[KEYS].copy()
    lineage = {}
    for source, target in residential_mapping.items():
        res[target] = residential[source]
        lineage[target] = {"source": "residential", "column": source, "scale": 1.0}
    for fuel in ("biomass", "gas", "oil"):
        target = f"residential heat {fuel}"
        source = f"residential heat {fuel} with cooking"
        res[target] = residential[source]
        lineage[target] = {"source": "residential", "column": source, "scale": 1.0}
    if "district heat share" in residential:
        res["district heat share"] = residential["district heat share"]
        lineage["district heat share"] = {"source": "residential", "column": "district heat share", "scale": 1.0}
    transport_cols = [col for col in TRANSPORT_COLUMNS if col in transport]
    transport = _values(transport, transport_cols, "transport")
    transport.loc[:, transport_cols] = transport.loc[:, transport_cols] * factor
    add_cols = [col for col in additional_columns if col in additional]
    additional = _values(additional, add_cols, "additional")
    merged = res.merge(additional[["country", "year"] + add_cols], on=["country", "year"],
                       validate="many_to_one", how="left")
    merged = merged.merge(transport[KEYS + transport_cols], on=KEYS, validate="one_to_one", how="left")
    for label, source, columns, scale in (("additional", additional, add_cols, 1.0),
                                          ("transport", transport, transport_cols, factor)):
        for col in columns:
            lineage[col] = {"source": label, "column": col, "scale": scale}
            multiplier = len(scenarios) if label == "additional" else 1
            if not np.isclose(merged[col].sum(), source[col].sum() * multiplier, rtol=1e-10, atol=1e-8):
                raise ValueError(f"{label}: join failed conservation for {col}")
    for col, info in lineage.items():
        if info["source"] == "residential" and not np.isclose(
                merged[col].sum(), residential[info["column"]].sum(), rtol=1e-10, atol=1e-8):
            raise ValueError(f"residential: join failed conservation for {col}")
    zeros = [col for col in ENERGY_COLUMNS if col not in merged]
    for col in zeros:
        merged[col] = 0.0
    if (merged["total road ev"] + merged["total road fcev"] > merged["total road"] + 1e-8).any():
        raise ValueError("transport: EV + FCEV exceeds total road")
    if (merged["electricity rail"] + merged["total rail hydrogen"] > merged["total rail"] + 1e-8).any():
        raise ValueError("transport: electricity + hydrogen exceeds total rail")
    metadata = {"status": "ready", "provisional": False, "lineage": lineage,
                "structural_zero_columns": zeros, "omitted_zero_columns": omitted,
                "diagnostic_submeasures": {"residential": residential_diagnostics, "transport": transport_diagnostics},
                "residential_coal_basis": ("explicit separate producer coal field" if "residential coal" in res
                                           else "legacy summary has no separate coal field; biomass may include coal"),
                "input_units": {"residential": "TWh", "additional": "TWh", "transport": transport_unit},
                "conservation": "validated per mapped column; additional replicated once per scenario; "
                                "navigation oil + hydrogen + ammonia + biomass equals domestic total; "
                                "residential end-use subsets bounded by carrier demand"}
    return _split_tables(merged, ENERGY_COLUMNS, years, scenarios, metadata)


def _emissions_readiness(metadata, allow_provisional, row_blockers=()):
    metadata = dict(metadata or {})
    blockers = list(row_blockers)
    blockers.extend(metadata.get("blockers", []))
    if metadata.get("status") != "ready":
        blockers.append("emissions readiness status is not ready")
    for field in ("factor_provenance", "ammonia_basis", "aluminium_basis"):
        if not metadata.get(field) or not str(metadata[field]).strip():
            blockers.append(f"missing emissions {field}")
    blockers = sorted(set(blockers))
    if blockers and not allow_provisional:
        raise ValueError("BLOCKER: " + "; ".join(blockers) + "; review only: allow_provisional=True")
    return {"status": "provisional" if blockers else "ready", "provisional": bool(blockers),
            "blockers": blockers, "emissions_readiness": metadata}


def build_industry_totals(industry_wide_df: pd.DataFrame, process_emissions_df: pd.DataFrame,
                          *, countries: Sequence[str], years=TARGET_YEARS, scenarios=SCENARIOS,
                          industry_units: Mapping[str, str] | None = None,
                          emissions_readiness: Mapping | None = None, allow_provisional: bool = False):
    """Preserve all 13 subsectors on example-compatible country/carrier rows.

    Industry keys: country/scenario/year/carrier. Declare per-carrier units in
    industry_units or attrs['units'], or a row unit column. Emissions summary
    keys add sector; measure is emissions_tCO2 or legacy emissions_MtCO2.
    """
    countries, years, scenarios = _scope(countries, years, scenarios)
    industry = _dimensions(industry_wide_df, "industry")
    _required(industry, ["carrier"] + list(INDUSTRY_SECTORS), "industry")
    industry["carrier"] = industry["carrier"].replace(CARRIER_ALIASES)
    _unique(industry, KEYS + ["carrier"], "industry")
    industry = _select(industry, countries, years, scenarios)
    _coverage(industry, countries, years, scenarios, "industry")
    unknown = set(industry["carrier"]) - (set(INDUSTRY_CARRIERS) - {"process emissions"})
    if unknown:
        raise ValueError(f"industry: unknown or embedded emissions carriers {sorted(unknown)}")
    omitted = _unmapped(industry, KEYS + ["carrier", "unit"] + list(INDUSTRY_SECTORS), "industry")
    industry = _values(industry, INDUSTRY_SECTORS, "industry")
    declared = industry_units if industry_units is not None else industry_wide_df.attrs.get("units", {})
    declared = {CARRIER_ALIASES.get(key, key): value for key, value in declared.items()}
    for carrier, rows in industry.groupby("carrier"):
        required_unit = INDUSTRY_UNITS[carrier]
        if "unit" in rows:
            if not rows["unit"].eq(required_unit).all():
                raise ValueError(f"industry: {carrier} must declare {required_unit}")
            if carrier in declared and declared[carrier] != required_unit:
                raise ValueError(f"industry: conflicting units for {carrier}")
        elif declared.get(carrier) != required_unit:
            raise ValueError(f"industry: {carrier} must declare {required_unit}; no blanket energy conversion")
    steel_other = [sector for sector in INDUSTRY_SECTORS if sector != "iron and steel"]
    if industry.loc[industry["carrier"] == "steel", steel_other].ne(0).any().any():
        raise ValueError("industry: steel activity outside iron and steel sector")
    emissions = _dimensions(process_emissions_df, "process emissions")
    _required(emissions, ["sector"], "process emissions")
    emissions["sector"] = emissions["sector"].replace({"paper, pulp and printing": "paper pulp and print"})
    _unique(emissions, KEYS + ["sector"], "process emissions summary")
    emissions = _select(emissions, countries, years, scenarios)
    _coverage(emissions, countries, years, scenarios, "process emissions")
    unknown = set(emissions["sector"]) - set(INDUSTRY_SECTORS)
    if unknown:
        raise ValueError(f"process emissions: unknown sectors {sorted(unknown)}")
    measures = [col for col in ("emissions_tCO2", "emissions_MtCO2") if col in emissions]
    if not measures:
        raise ValueError("process emissions: declare emissions_tCO2 or emissions_MtCO2")
    measure = measures[0]
    unit = "tCO2/a" if measure == "emissions_tCO2" else "MtCO2/a"
    if "unit" in emissions and not emissions["unit"].eq(unit).all():
        raise ValueError(f"process emissions: {measure} contradicts unit; expected {unit}")
    if "unit" in process_emissions_df.attrs and process_emissions_df.attrs["unit"] != unit:
        raise ValueError("process emissions: contradictory attrs unit")
    emissions = _values(emissions, measures, "process emissions")
    if len(measures) == 2 and not np.allclose(emissions["emissions_tCO2"],
            emissions["emissions_MtCO2"] * 1e6, rtol=1e-9, atol=1e-8):
        raise ValueError("process emissions: inconsistent tCO2 and MtCO2 declarations")
    row_blockers = []
    review_fields = ["emissions_units", "gas_basis", "readiness", "ready_for_export", "blockers"]
    if set(review_fields).intersection(emissions.columns):
        _required(emissions, review_fields, "process emissions review")
        if not emissions["emissions_units"].eq(unit).all() or not emissions["gas_basis"].eq("CO2").all():
            raise ValueError("process emissions: must be physical CO2, not CO2e/PFCs, in declared units")
        flags = emissions["ready_for_export"].astype(str).str.lower()
        if not flags.isin(["true", "false"]).all():
            raise ValueError("process emissions: invalid ready_for_export flags")
        if not emissions["readiness"].isin(["accepted", "provisional", "blocked"]).all():
            raise ValueError("process emissions: unknown readiness status")
        for value in emissions["blockers"]:
            blockers = json.loads(value) if isinstance(value, str) else value
            if not isinstance(blockers, list) or any(not isinstance(b, str) or not b for b in blockers):
                raise ValueError("process emissions: blockers must be arrays of nonempty strings")
            row_blockers.extend(blockers)
        if not flags.eq("true").all() or not emissions["readiness"].eq("accepted").all():
            row_blockers.append("producer process-emissions rows are not accepted")
        # Use the producer's own acceptance gate for the new summary contract.
        # Keep this import lazy; importing this exporter must not load calculators.
        from industry.scripts.calculate_process_emissions import require_accepted_process_emissions

        require_accepted_process_emissions(emissions, allow_provisional=allow_provisional)
    emitting = ("iron and steel", "chemical and petrochemical", "non-metallic minerals",
                "non-ferrous metals", "paper pulp and print")
    actual = set(emissions[KEYS + ["sector"]].itertuples(index=False, name=None))
    expected = set(product(countries, scenarios, years, emitting))
    if expected - actual:
        raise ValueError(f"process emissions: missing sector coverage {sorted(expected - actual)[:8]}")
    readiness = emissions_readiness if emissions_readiness is not None else process_emissions_df.attrs.get("readiness")
    metadata = _emissions_readiness(readiness, allow_provisional, row_blockers)
    emissions["value"] = emissions[measure] * (1e6 if measure == "emissions_MtCO2" else 1.0)
    emissions_wide = emissions.pivot(index=KEYS, columns="sector", values="value")
    # Only absent non-emitting sectors are structural zeros. Existing NaNs have
    # already failed _values; never fill missing physical CO2 or energy values.
    emissions_index = pd.MultiIndex.from_product([countries, scenarios, years], names=KEYS)
    emissions_columns = pd.MultiIndex.from_product([countries, scenarios, years, INDUSTRY_SECTORS],
                                                  names=KEYS + ["sector"])
    missing_emissions = emissions_columns.difference(emissions.set_index(KEYS + ["sector"]).index)
    for country, scenario, year, sector in missing_emissions:
        emissions_wide.loc[(country, scenario, year), sector] = 0.0
    emissions_wide = emissions_wide.reindex(index=emissions_index, columns=list(INDUSTRY_SECTORS))
    emissions_wide.columns.name = None
    emissions_wide = emissions_wide.reset_index().assign(carrier="process emissions")
    output = pd.concat([industry[KEYS + ["carrier"] + list(INDUSTRY_SECTORS)], emissions_wide],
                       ignore_index=True).set_index(KEYS + ["carrier"])
    expected_index = pd.MultiIndex.from_product([countries, scenarios, years, INDUSTRY_CARRIERS],
                                               names=KEYS + ["carrier"])
    missing_rows = expected_index.difference(output.index)
    output = output.reindex(expected_index)
    output.loc[missing_rows, :] = 0.0  # absent sparse quantity rows only
    output = _values(output, INDUSTRY_SECTORS, "industry output")
    _unique(output.reset_index(), KEYS + ["carrier"], "industry output")

    # Compare every country/scenario/year/subsector separately in native units,
    # both by legacy quantity label and by physical quantity class. No mixed sum.
    source = pd.concat([industry[KEYS + ["carrier"] + list(INDUSTRY_SECTORS)], emissions_wide],
                       ignore_index=True)
    for dimension, classes in (("carrier", None), ("quantity_class", INDUSTRY_QUANTITY_CLASSES)):
        before, after = source.copy(), output.reset_index()
        if classes is not None:
            before[dimension] = before["carrier"].map(classes)
            after[dimension] = after["carrier"].map(classes)
        grouping = KEYS + [dimension]
        expected = before.groupby(grouping)[list(INDUSTRY_SECTORS)].sum()
        actual = after.groupby(grouping)[list(INDUSTRY_SECTORS)].sum()
        expected = expected.reindex(actual.index, fill_value=0.0)
        if not np.isfinite(actual.to_numpy()).all() or not np.allclose(
                actual.to_numpy(), expected.to_numpy(), rtol=1e-10, atol=1e-8):
            raise ValueError(f"industry: failed conservation by subsector and {dimension}")
    metadata.update({"input_emissions_unit": unit, "heat_mapping": "heat -> low-temperature heat (all supplied heat)",
                     "biomass_mapping": "solid biomass -> biomass (example label)", "omitted_zero_columns": omitted,
                     "structural_zero_rows": [dict(zip(KEYS + ["carrier"], key)) for key in missing_rows],
                     "structural_zero_emissions_sectors": [dict(zip(KEYS + ["sector"], key))
                                                            for key in missing_emissions],
                     "aggregation": "none across subsectors; emissions summary sector -> subsector",
                     "conservation": "validated per country/scenario/year/subsector and quantity label/class in native units"})
    tables = {}
    for scenario, year in product(scenarios, years):
        table = output.xs((scenario, year), level=("scenario", "year"))
        table = table.reindex(pd.MultiIndex.from_product([sorted(countries), INDUSTRY_CARRIERS],
                                                        names=["country", "carrier"]))
        table.attrs["metadata"] = dict(metadata)
        tables[(scenario, year)] = table
    return tables


def write_export_tables(tables, output_dir: Path, kind: str):
    """Write CSVs and adjacent *.units.json sidecars; return CSV paths."""
    if kind not in ("energy", "industry"):
        raise ValueError("kind must be energy or industry")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for (scenario, year), table in tables.items():
        filename = (f"energy_totals_{scenario}_{year}.csv" if kind == "energy"
                    else f"industry_totals_{year}_{scenario}.csv")
        path = output_dir / filename
        metadata = dict(table.attrs["metadata"])
        metadata.update({"schema_version": 2, "file": filename, "scenario": scenario, "year": int(year),
                         "country_index": {"name": "country", "encoding": "ISO3166-1 alpha-2",
                                           "values": list(table.index.get_level_values("country").unique())},
                         "orientation": ("country rows, measure columns" if kind == "energy"
                                         else "country/carrier rows, subsector columns"),
                         "index_fields": ["country"] if kind == "energy" else ["country", "carrier"],
                         "time_resolution": "annual", "scenario_mapping": "identity; no EL/RF mapping approved"})
        if kind == "energy":
            metadata["columns"] = {col: {"unit": "fraction" if col == "district heat share" else "TWh/a"}
                                   for col in table.columns}
        else:
            metadata.update({
                "columns": {col: {"unit_by_index_field": "carrier"} for col in table.columns},
                "quantity_index": {
                    "field": "carrier", "legacy_field": True,
                    "description": "Legacy carrier dimension includes energy, products and emissions; not all rows are energy carriers.",
                    "values": {label: {"quantity_class": INDUSTRY_QUANTITY_CLASSES[label], "unit": INDUSTRY_UNITS[label]}
                               for label in INDUSTRY_CARRIERS},
                },
                "quantity_classes": {name: {"unit": unit, "index_values": [label for label in INDUSTRY_CARRIERS
                                                                         if INDUSTRY_QUANTITY_CLASSES[label] == name]}
                                     for name, unit in (("energy", "MWh/a"), ("product_activity", "tSteel/a"),
                                                        ("process_emissions", "tCO2/a"))},
            })
        encoded = json.dumps(metadata, indent=2, allow_nan=False) + "\n"
        path.with_suffix(".units.json").write_text(encoded, encoding="utf-8")
        table.to_csv(path, index=True)
        paths.append(path)
    return paths


def export_energy_totals_by_scenario_year(residential_output_dir: Path, additional_output_dir: Path,
                                         transport_output_dir: Path, output_dir: Path, *, countries,
                                         years=TARGET_YEARS, scenarios=SCENARIOS, transport_unit="TWh"):
    tables = build_energy_totals(load_residential_data(residential_output_dir),
        load_additional_sectors_data(additional_output_dir),
        load_transport_data(transport_output_dir, years=years, scenarios=scenarios, unit=transport_unit),
        countries=countries, years=years, scenarios=scenarios, transport_unit=transport_unit)
    return write_export_tables(tables, output_dir, "energy")


def export_industry_totals_by_scenario_year(industry_wide_df: pd.DataFrame,
                                           process_emissions_df: pd.DataFrame, output_dir: Path, **kwargs):
    return write_export_tables(build_industry_totals(industry_wide_df, process_emissions_df, **kwargs),
                               output_dir, "industry")


def main(argv=None) -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    defaults = {
        "residential_output_dir": root / "residential/output_data",
        "additional_output_dir": root / "additional sectors/output_data",
        "transport_output_dir": root / "transport/output_data",
        "config_path": root / "industry/output_data/CONFIG/INDUSTRY_CONFIG.csv",
        "interim_dir": root / "industry/output_data/interim_data",
        "output_dir": root / "pypsa_input",
    }
    for name, default in defaults.items():
        parser.add_argument("--" + name.replace("_", "-"), "--" + name, dest=name, type=Path, default=default)
    parser.add_argument("--countries", nargs="+", help="Exact names/ISO2; default: config country columns")
    parser.add_argument("--years", nargs="+", type=int, default=list(TARGET_YEARS))
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIOS, default=list(SCENARIOS))
    parser.add_argument("--transport-unit", choices=("GWh", "TWh"), default="TWh")
    parser.add_argument("--industry-units", type=Path, help="JSON per-carrier units if calculator attrs lack them")
    parser.add_argument("--process-emissions-path", type=Path)
    parser.add_argument("--emissions-readiness", type=Path, help="Reviewed provenance/ammonia/aluminium JSON")
    parser.add_argument("--allow-provisional", "--allow_provisional", action="store_true", help="Review fixtures only")
    args = parser.parse_args(argv)
    config = _read_csv(args.config_path)
    dimensions = {"metric_1", "metric_2", "metric_3", "metric_4", "year", "scenario", "units"}
    countries = args.countries or [col for col in config if col not in dimensions]
    countries, years, scenarios = _scope(countries, args.years, args.scenarios)
    calculator_countries = [col for col in config if col not in dimensions and get_iso_code(col) in countries]
    if set(map(get_iso_code, calculator_countries)) != set(countries):
        raise ValueError("industry config: missing requested country coverage")
    energy = build_energy_totals(load_residential_data(args.residential_output_dir),
        load_additional_sectors_data(args.additional_output_dir),
        load_transport_data(args.transport_output_dir, years=years, scenarios=scenarios, unit=args.transport_unit),
        countries=countries, years=years, scenarios=scenarios, transport_unit=args.transport_unit)
    from industry.scripts.calculate_final_energy_demand import FinalEnergyCalculator

    calculator = FinalEnergyCalculator(args.config_path, args.interim_dir,
                                       refresh_years=list(years), refresh_scenarios=list(scenarios),
                                       countries=calculator_countries)
    results = calculator.calculate_all_detailed_sectors(years=list(years), scenarios=list(scenarios))
    wide = calculator.pivot_to_wide_format(results)
    if "units" not in wide.attrs and "units" in results.attrs:
        wide.attrs["units"] = results.attrs["units"]
    units = (json.loads(args.industry_units.read_text(encoding="utf-8")) if args.industry_units
             else wide.attrs.get("units", CALCULATOR_UNITS))
    emissions_path = args.process_emissions_path or args.interim_dir / "process_emissions_summary.csv"
    emissions = _read_csv(emissions_path)
    readiness_path = args.emissions_readiness or emissions_path.with_suffix(".readiness.json")
    producer_readiness = args.interim_dir / "process_emissions_readiness.json"
    if not args.emissions_readiness and not readiness_path.exists() and producer_readiness.exists():
        readiness_path = producer_readiness
    if args.emissions_readiness and not readiness_path.exists():
        raise FileNotFoundError(readiness_path)
    readiness = json.loads(readiness_path.read_text(encoding="utf-8")) if readiness_path.exists() else None
    industry = build_industry_totals(wide, emissions, countries=countries, years=years, scenarios=scenarios,
                                     industry_units=units, emissions_readiness=readiness,
                                     allow_provisional=args.allow_provisional)
    if any(table.attrs["metadata"]["provisional"] for table in industry.values()):
        for table in energy.values():
            table.attrs["metadata"].update({"status": "provisional", "provisional": True,
                                            "blockers": ["paired industry emissions are provisional"]})
    paths = write_export_tables(energy, args.output_dir, "energy")
    paths += write_export_tables(industry, args.output_dir, "industry")
    print(f"Exported {len(paths)} CSVs with unit sidecars to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
