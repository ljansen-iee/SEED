import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / "industry_config.xlsx"

xls = pd.ExcelFile(EXCEL_PATH)

print("Excel loaded OK")
print("Sheets:", xls.sheet_names)
df = pd.read_excel(xls, "Sheet1")
print(df.head())
row = df[
    (df["Metric Name"] == "Steel production per year") &
    (df["Year"] == 2050) &
    (df["Scenario"] == "sc_b")
]

print("CAGR value:", row["default"].values)
