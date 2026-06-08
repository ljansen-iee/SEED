from industry.utils.helpers import get_historical_sector_data
from pathlib import Path

data = get_historical_sector_data(Path('input_data/unsdata_historical'), 'Egypt', 'Industry n.e.s')
if data:
    print('Historical data (GWh):')
    for year, gwh in sorted(data.items()):
        print(f'  {year}: {gwh:,.0f} GWh = {gwh*1000:,.0f} MWh')
    base_2020 = data.get(2020, 'N/A')
    print(f'\nBase year 2020: {base_2020}')
else:
    print('No data found')
