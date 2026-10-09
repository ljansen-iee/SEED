# Contributing

Thank you for contributing to Sectoral Energy Demands!

## How to add a new country

Adding a country requires providing data for each sector you want to model.

### 1 — Download UNSD energy-balance data

1. Go to <https://unstats.un.org/unsd/energystats/dataPortal/>
2. Select your country and download the energy balance CSV for all available years.
3. Place it in `data/country_specific/` with the filename `UNSD_{Country}-{Year}.csv`.

### 2 — Download SSP population & GDP projections

1. Go to <https://climate-solutions-explorer.pik-potsdam.de/>
2. Select your country, navigate to the Population and GDP charts.
3. Download the chart CSV for SSP1–SSP5.
4. Place the files in `transport/input_data/country_specific/` and
   `residential/input_data/country_specific/` with the names:
   - `chart-data_pop_{Country}.csv`
   - `chart-data_gdp_{Country}.csv`

### 3 — Add the country to `trans_config.csv`

Add a row for each metric you want to override. At minimum, confirm the default
base year and SSP pathway are correct for your country.

### 4 — Run and validate

```bash
python build_shares.py
python build_CAGR.py
python -m transport.build_transport_config
python -m transport.build_final_energy_demand
```

Check the output CSVs for implausible values (negative demand, zero shares, etc.).

---

## How to add a new sector or sub-sector

1. Create a new directory `{sector}/` with the standard structure:
   - `build_macro_indicators.py`
   - `build_energy_intensities.py`
   - `build_technology_shares.py`
   - `build_CAGR.py`
   - `build_final_energy_demand.py`
   - `helpers.py`
   - `main_{sector}.py`
2. Follow the common pipeline pattern described in
   [Methodology Overview](methodology/overview.md).
3. Add the sector to `build_pypsa_energy_totals.py` if it should feed into PyPSA.

---

## Code style

- Python 3.10, PEP 8.
- Use **Google-style docstrings** for all public functions so that
  `mkdocstrings` can auto-generate API documentation.
- Keep one `build_*.py` script per concern (no monolithic files).

## Reporting issues

Open an issue on the
[GitHub project page](https://github.com/ljansen-iee/SEED/issues).
