
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "external"
OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Loading demand summary...")
summary = pd.read_csv(
    OUTPUT_DIR / "m5_demand_summary.csv"
)

print("Reading calendar...")
calendar = pd.read_csv(
    DATA_DIR / "calendar.csv",
    usecols=["d", "wm_yr_wk"]
)

day_columns = [
    column for column in calendar["d"].tolist()
    if column.startswith("d_")
]
recent_days = set(day_columns[-56:])

recent_calendar = calendar[
    calendar["d"].isin(recent_days)
]
recent_weeks = set(recent_calendar["wm_yr_wk"].dropna())

print("Recent weeks:", len(recent_weeks))
print("Reading prices in chunks...")

price_path = DATA_DIR / "sell_prices.csv"
price_columns = [
    "store_id", "item_id", "wm_yr_wk", "sell_price"
]

latest_by_pair = {}

for chunk in pd.read_csv(
    price_path,
    usecols=price_columns,
    chunksize=500_000
):
    chunk = chunk[
        chunk["wm_yr_wk"].isin(recent_weeks)
    ]

    if chunk.empty:
        continue

    chunk = chunk.merge(
        summary[["item_id", "store_id"]].drop_duplicates(),
        on=["item_id", "store_id"],
        how="inner"
    )

    if chunk.empty:
        continue

    chunk = chunk.sort_values("wm_yr_wk")

    for row in chunk.itertuples(index=False):
        key = (row.item_id, row.store_id)
        previous = latest_by_pair.get(key)

        if previous is None or row.wm_yr_wk > previous[0]:
            latest_by_pair[key] = (
                row.wm_yr_wk,
                row.sell_price
            )

print("Building output...")

prices = pd.DataFrame(
    [
        {
            "item_id": item_id,
            "store_id": store_id,
            "wm_yr_wk": week,
            "sell_price": price
        }
        for (item_id, store_id), (week, price)
        in latest_by_pair.items()
    ]
)

output_path = OUTPUT_DIR / "m5_latest_prices.csv"
prices.to_csv(output_path, index=False)

print("\nPrice processing complete!")
print("Price records:", len(prices))
print("Output:", output_path)
print("\nSample prices:")
print(prices.head(10).to_string(index=False))