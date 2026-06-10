"""Compatibility wrapper for manual CAGR report export.

The main workflow now auto-generates these files during
generate_industry_config.py. This script remains as a thin manual entrypoint.
"""

from pathlib import Path

from industry.utils.cagr_reporting import export_cagr_reports_from_config_path


def extract_cagr_values():
    """Regenerate readable CAGR CSVs from the latest INDUSTRY_CONFIG.csv."""
    base_dir = Path(__file__).resolve().parents[1]
    config_path = base_dir / 'output_data' / 'CONFIG' / 'INDUSTRY_CONFIG.csv'
    output_dir = base_dir / 'output_data' / 'interim_data'

    print("=" * 80)
    print("REGENERATING CAGR REPORTS FROM INDUSTRY_CONFIG.csv")
    print("=" * 80)

    export_cagr_reports_from_config_path(config_path=config_path, output_dir=output_dir)
    print(f"\nOutput directory: {output_dir}")


if __name__ == '__main__':
    extract_cagr_values()
