import os, glob
import pandas as pd

def merge_all_country_indicators(base_results="results"):
    # Find all Excel files like results/<Country>/transport_indicators.xlsx
    files = glob.glob(os.path.join(base_results, "*", "transport_indicators.xlsx"))
    if not files:
        print(" No transport_indicators.xlsx files found under", base_results)
        return

    # Read and combine all dataframes
    all_dfs = []
    for f in files:
        try:
            df = pd.read_excel(f)
            country = os.path.basename(os.path.dirname(f))
            df["country"] = country  # add country column
            all_dfs.append(df)
        except Exception as e:
            print(f" Error reading {f}: {e}")

    merged = pd.concat(all_dfs, ignore_index=True)
    output_path = os.path.join(base_results, "all_transport_indicators.xlsx")
    merged.to_excel(output_path, index=False)

    print(f" Merged file saved at {output_path}")
    print(f"   Total rows: {len(merged)}")

if __name__ == "__main__":
    merge_all_country_indicators()
