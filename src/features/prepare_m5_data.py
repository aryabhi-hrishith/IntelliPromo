
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data" / "external"
OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sales_path = DATA_DIR / "sales_train_validation.csv"

print("Loading Walmart sales data...")

# Load product/store identifiers and the most recent 56 days
header = pd.read_csv(sales_path, nrows=0).columns.tolist()
day_columns = [c for c in header if c.startswith("d_")]
recent_days = day_columns[-56:]

use_columns = [
    "id", "item_id", "dept_id",
    "cat_id", "store_id", "state_id"
] + recent_days

sales = pd.read_csv(sales_path, usecols=use_columns)

# Compare the first and second 28-day periods
first_28 = recent_days[:28]
last_28 = recent_days[28:]

sales["previous_28d_units"] = sales[first_28].sum(axis=1)
sales["recent_28d_units"] = sales[last_28].sum(axis=1)
sales["average_daily_units"] = sales["recent_28d_units"] / 28

sales["demand_change_pct"] = (
    (sales["recent_28d_units"] - sales["previous_28d_units"])
    / sales["previous_28d_units"].replace(0, float("nan"))
) * 100

# Remove the daily columns and retain the useful summary
summary_columns = [
    "id", "item_id", "dept_id", "cat_id",
    "store_id", "state_id",
    "previous_28d_units", "recent_28d_units",
    "average_daily_units", "demand_change_pct"
]

summary = sales[summary_columns].copy()

summary["demand_change_pct"] = (
    summary["demand_change_pct"].fillna(0).round(2)
)
summary["average_daily_units"] = (
    summary["average_daily_units"].round(3)
)

output_path = OUTPUT_DIR / "m5_demand_summary.csv"
summary.to_csv(output_path, index=False)

print("\nProcessing complete!")
print("Records:", len(summary))
print("Output:", output_path)
print("\nTop 10 products by recent sales:")
print(
    summary.sort_values("recent_28d_units", ascending=False)
    [["item_id", "store_id", "recent_28d_units",
      "average_daily_units", "demand_change_pct"]]
    .head(10).to_string(index=False)
)