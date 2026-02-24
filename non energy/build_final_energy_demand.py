from pathlib import Path
import pandas as pd

from build_non_energy_shares import (
    _default_share_dict,
    _discover_countries,
    _discover_country_years,
    get_non_energy_shares,
    get_non_energy_shares_historical_average,
)


def _get_candidate_dirs(base_path: Path):
    return [
        Path(base_path),
        Path(__file__).resolve().parents[1] / "data" / "country_specific",
    ]


def _clean_val(val):
    if pd.isna(val):
        return 0.0
    s_val = str(val).strip()
    if s_val in ["---", "", "None", "-"]:
        return 0.0
    try:
        clean_s = s_val.replace('*', '').replace('-', '')
        return float(clean_s) if clean_s else 0.0
    except ValueError:
        return 0.0


def get_non_energy_total_GWh(
    base_path: Path,
    country: str,
    year: int,
    sector_name: str = "Non-energy use",
):
    filename = f"UNSD_{country}-{year}.csv"
    candidates = [directory / filename for directory in _get_candidate_dirs(base_path)]
    file_path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])

    if not file_path.exists():
        return 0.0

    df = pd.read_csv(file_path)
    sector_col = "Transactions(down)/Commodity(right)"
    row = df[df[sector_col].str.strip().str.lower() == sector_name.lower()]

    if row.empty:
        return 0.0

    total_tj = _clean_val(row["Total Energy"].iloc[0])
    return round(total_tj * 0.277778, 2)


def _fuel_demand_from_total(total_energy_gwh: float, shares: dict):
    return {
        fuel: round(total_energy_gwh * share, 6)
        for fuel, share in shares.items()
    }


def _rename_fuel_columns_to_non_energy(fuel_demand: dict):
    return {
        f"non energy {fuel}": value
        for fuel, value in fuel_demand.items()
    }


def build_non_energy_fuel_demand_history_and_future(
    base_path: Path,
    output_csv_path: Path,
    base_year_for_projection: int,
    cagr: float = 0.03,
    future_years: list = None,
    sector_name: str = "Non-energy use",
):
    if future_years is None:
        future_years = [2030, 2035, 2040, 2045, 2050]

    countries = _discover_countries(base_path=base_path)
    fuels = list(_default_share_dict().keys())

    rows = []
    for country in countries:
        historical_years = _discover_country_years(base_path=base_path, country=country)

        for historical_year in historical_years:
            total_gwh = get_non_energy_total_GWh(
                base_path=base_path,
                country=country,
                year=historical_year,
                sector_name=sector_name,
            )
            if total_gwh <= 0:
                continue

            historical_shares = get_non_energy_shares(
                base_path=base_path,
                country=country,
                year=historical_year,
                sector_name=sector_name,
            )
            historical_fuel_demand = _fuel_demand_from_total(
                total_energy_gwh=total_gwh,
                shares=historical_shares,
            )
            historical_fuel_demand = _rename_fuel_columns_to_non_energy(historical_fuel_demand)

            rows.append(
                {
                    "country": country,
                    "year": historical_year,
                    **historical_fuel_demand,
                }
            )

        base_year_total_gwh = get_non_energy_total_GWh(
            base_path=base_path,
            country=country,
            year=base_year_for_projection,
            sector_name=sector_name,
        )
        if base_year_total_gwh <= 0:
            continue

        average_shares = get_non_energy_shares_historical_average(
            base_path=base_path,
            country=country,
            sector_name=sector_name,
        )

        for future_year in future_years:
            if future_year <= base_year_for_projection:
                continue

            year_delta = future_year - base_year_for_projection
            projected_total_gwh = round(
                base_year_total_gwh * ((1 + cagr) ** year_delta),
                6,
            )
            projected_fuel_demand = _fuel_demand_from_total(
                total_energy_gwh=projected_total_gwh,
                shares=average_shares,
            )
            projected_fuel_demand = _rename_fuel_columns_to_non_energy(projected_fuel_demand)

            rows.append(
                {
                    "country": country,
                    "year": future_year,
                    **projected_fuel_demand,
                }
            )

    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    output_columns = ["country", "year", *[f"non energy {fuel}" for fuel in fuels]]
    output_df = pd.DataFrame(rows)
    if output_df.empty:
        output_df = pd.DataFrame(columns=output_columns)
    else:
        output_df = output_df[output_columns].sort_values(by=["country", "year"]).reset_index(drop=True)

    output_df.to_csv(output_csv_path, index=False)
    return output_csv_path


if __name__ == "__main__":
    base_path = Path(__file__).resolve().parents[1] / "data" / "country_specific"
    output_path = Path(__file__).resolve().parent / "output_data" / "non_energy_fuel_demand_history_future.csv"

    output_file = build_non_energy_fuel_demand_history_and_future(
        base_path=base_path,
        output_csv_path=output_path,
        base_year_for_projection=2023,
        cagr=0.03,
    )
    print(f"Saved non-energy fuel demand CSV to: {output_file}")
