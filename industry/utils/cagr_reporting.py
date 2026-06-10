"""Utilities for exporting readable CAGR reports from INDUSTRY_CONFIG data."""

from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd


CONFIG_METADATA_COLUMNS = [
    'metric_1',
    'metric_2',
    'metric_3',
    'metric_4',
    'year',
    'scenario',
    'units',
]


def _resolve_countries(df_config: pd.DataFrame, countries: Optional[Iterable[str]] = None) -> List[str]:
    if countries is not None:
        return [country for country in countries if country in df_config.columns]

    return [column for column in df_config.columns if column not in CONFIG_METADATA_COLUMNS]


def export_cagr_reports(
    df_config: pd.DataFrame,
    output_dir: Path,
    countries: Optional[Iterable[str]] = None,
    verbose: bool = True,
) -> dict:
    """Export readable CAGR CSVs to the interim output directory."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    country_columns = _resolve_countries(df_config, countries)
    cagr_rows = df_config[df_config['metric_2'] == 'cagr'].copy()

    if verbose:
        print("\n" + "=" * 60)
        print("AUTO-GENERATING CAGR REPORTS")
        print("=" * 60)
        print(f"Total CAGR rows: {len(cagr_rows)}")

    production_cagr = cagr_rows[
        ~cagr_rows['metric_3'].str.contains('energy intensity', case=False, na=False)
    ].copy()
    intensity_cagr = cagr_rows[
        cagr_rows['metric_3'].str.contains('energy intensity', case=False, na=False)
    ].copy()

    production_summary = []
    for _, row in production_cagr.iterrows():
        for country in country_columns:
            production_summary.append({
                'sector': row['metric_1'],
                'metric': row['metric_3'],
                'period': row['year'],
                'scenario': row['scenario'],
                'country': country,
                'cagr': row[country],
            })

    intensity_summary = []
    for _, row in intensity_cagr.iterrows():
        for country in country_columns:
            intensity_summary.append({
                'sector': row['metric_1'],
                'technology_route': row['metric_3'],
                'period': row['year'],
                'scenario': row['scenario'],
                'country': country,
                'cagr': row[country],
            })

    df_production = pd.DataFrame(production_summary)
    df_intensity = pd.DataFrame(intensity_summary)

    output_production = output_dir / 'production_cagr.csv'
    output_intensity = output_dir / 'intensity_cagr.csv'
    output_summary = output_dir / 'intensity_cagr_summary.csv'

    df_production.to_csv(output_production, index=False)
    df_intensity.to_csv(output_intensity, index=False)

    if country_columns and not intensity_cagr.empty:
        reference_country = country_columns[0]
        intensity_pivot = intensity_cagr.groupby(
            ['metric_1', 'metric_3', 'scenario']
        )[reference_country].first().reset_index()
        intensity_pivot = intensity_pivot.pivot(
            index=['metric_1', 'metric_3'],
            columns='scenario',
            values=reference_country,
        ).reset_index()
    else:
        reference_country = None
        intensity_pivot = pd.DataFrame(columns=['metric_1', 'metric_3'])

    intensity_pivot.to_csv(output_summary, index=False)

    if verbose:
        print(f"✓ Written → {output_production}")
        print(f"  Rows: {len(df_production)}")
        print(f"✓ Written → {output_intensity}")
        print(f"  Rows: {len(df_intensity)}")
        print(f"✓ Written → {output_summary}")
        print(f"  Rows: {len(intensity_pivot)}")
        if reference_country is not None:
            print(f"  Summary reference country: {reference_country}")

    return {
        'production': output_production,
        'intensity': output_intensity,
        'summary': output_summary,
    }


def export_cagr_reports_from_config_path(config_path: Path, output_dir: Optional[Path] = None) -> dict:
    """Load INDUSTRY_CONFIG.csv from disk and export CAGR reports."""
    config_path = Path(config_path)
    if output_dir is None:
        output_dir = config_path.parents[1] / 'interim_data'

    df_config = pd.read_csv(config_path)
    return export_cagr_reports(df_config=df_config, output_dir=output_dir)