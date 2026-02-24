import pandas as pd
from pathlib import Path


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


def _default_share_dict():
    return {
        'oil': 0.0,
        'gas': 0.0,
        'electricity': 0.0,
        'coal': 0.0,
        'biomass': 0.0,
        'ammonia': 0.0,
    }


def _validate_share_sum(shares: dict, tolerance: float = 1e-3):
    share_sum = round(sum(shares.values()), 6)
    is_valid = share_sum > 0 and abs(share_sum - 1.0) <= tolerance
    return share_sum, is_valid


def _get_candidate_dirs(base_path: Path):
    return [
        Path(base_path),
        Path(__file__).resolve().parents[1] / "data" / "country_specific",
    ]


def _discover_country_years(base_path: Path, country: str):
    years = set()
    prefix = f"UNSD_{country}-"
    suffix = ".csv"

    for directory in _get_candidate_dirs(base_path):
        if not directory.exists():
            continue
        for file_path in directory.glob(f"{prefix}*{suffix}"):
            name = file_path.name
            year_text = name[len(prefix):-len(suffix)]
            if year_text.isdigit():
                years.add(int(year_text))

    return sorted(years)


def _discover_countries(base_path: Path):
    countries = set()
    prefix = "UNSD_"
    suffix = ".csv"

    for directory in _get_candidate_dirs(base_path):
        if not directory.exists():
            continue
        for file_path in directory.glob(f"{prefix}*{suffix}"):
            name = file_path.name
            if not name.startswith(prefix) or not name.endswith(suffix):
                continue
            country_and_year = name[len(prefix):-len(suffix)]
            if "-" not in country_and_year:
                continue
            country, year_text = country_and_year.rsplit("-", 1)
            if country and year_text.isdigit():
                countries.add(country)

    return sorted(countries)


def get_non_energy_shares(base_path: Path, country: str, year: int, sector_name: str = "Non-energy use"):
    """
    Calculates decimal shares (0-1) of each fuel for the Non-energy use sector.
    """
    filename = f"UNSD_{country}-{year}.csv"
    candidates = [directory / filename for directory in _get_candidate_dirs(base_path)]
    file_path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])

    fuel_mapping = {
        'oil': ['Primary Oil', 'Oil Products'],
        'gas': ['Natural Gas'],
        'electricity': ['Nuclear', 'Electricity'],
        'coal': ['Primary Coal and Peat', 'Coal and Peat Products'],
        'biomass': ['Biofuels and Waste'],
        'ammonia': [],
    }

    if not file_path.exists():
        return _default_share_dict()

    df = pd.read_csv(file_path)
    sector_col = "Transactions(down)/Commodity(right)"
    row = df[df[sector_col].str.strip().str.lower() == sector_name.lower()]

    if row.empty:
        return _default_share_dict()

    total_tj = _clean_val(row["Total Energy"].iloc[0])

    if total_tj == 0:
        return _default_share_dict()

    shares = {}
    for cat, headers in fuel_mapping.items():
        cat_sum = sum([_clean_val(row[h].iloc[0]) for h in headers if h in df.columns])
        shares[cat] = round(cat_sum / total_tj, 6)

    return shares


def get_non_energy_shares_historical_average(
    base_path: Path,
    country: str,
    years: list = None,
    sector_name: str = "Non-energy use",
):
    """
    Calculates average fuel shares (decimal basis, 0-1) across multiple historical years
    for the Non-energy use sector.
    """
    if years is None:
        years = _discover_country_years(base_path=base_path, country=country)

    if not years:
        return _default_share_dict()

    valid_shares = []
    for historical_year in years:
        year_shares = get_non_energy_shares(
            base_path=base_path,
            country=country,
            year=historical_year,
            sector_name=sector_name,
        )
        if any(value > 0 for value in year_shares.values()):
            valid_shares.append(year_shares)

    if not valid_shares:
        return _default_share_dict()

    averaged = {}
    categories = valid_shares[0].keys()
    for category in categories:
        averaged[category] = round(
            sum(share[category] for share in valid_shares) / len(valid_shares),
            4,
        )

    return averaged


def export_non_energy_shares_all_countries(
    base_path: Path,
    output_csv_path: Path,
    year: int = None,
    sector_name: str = "Non-energy use",
):
    countries = _discover_countries(base_path=base_path)
    if not countries:
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["country", "share_mode", "year", *_default_share_dict().keys()]).to_csv(output_csv_path, index=False)
        return output_csv_path

    rows = []
    for country in countries:
        if year is None:
            shares = get_non_energy_shares_historical_average(
                base_path=base_path,
                country=country,
                sector_name=sector_name,
            )
            share_sum, share_sum_is_valid = _validate_share_sum(shares)
            row = {
                "country": country,
                "share_mode": "historical_average",
                "year": "all_available",
                "share_sum": share_sum,
                "share_sum_is_valid": share_sum_is_valid,
                **shares,
            }
        else:
            shares = get_non_energy_shares(
                base_path=base_path,
                country=country,
                year=year,
                sector_name=sector_name,
            )
            share_sum, share_sum_is_valid = _validate_share_sum(shares)
            row = {
                "country": country,
                "share_mode": "single_year",
                "year": year,
                "share_sum": share_sum,
                "share_sum_is_valid": share_sum_is_valid,
                **shares,
            }
        rows.append(row)

    output_df = pd.DataFrame(rows)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_csv_path, index=False)
    return output_csv_path


if __name__ == "__main__":
    base_path = Path(__file__).resolve().parents[1] / "data" / "country_specific"
    output_path = Path(__file__).resolve().parent / "output_data" / "non_energy_shares_all_countries.csv"
    output_file = export_non_energy_shares_all_countries(
        base_path=base_path,
        output_csv_path=output_path,
        year=None,
        sector_name="Non-energy use",
    )
    print(f"Saved non-energy shares CSV to: {output_file}")
