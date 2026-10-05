
import pandas as pd
from pathlib import Path

DATA_DIR = Path("data/external")

# Read a small sample instead of loading the 116 MB file fully
sales_path = DATA_DIR / "sales_train_validation.csv"

df = pd.read_csv(sales_path, nrows=5)

print("Dataset columns:")
print(df.columns.tolist())

print("\nFirst 5 rows:")
print(df.to_string(index=False))

print("\nShape of the full dataset (row count only):")
with open(sales_path, "r", encoding="utf-8") as f:
    row_count = sum(1 for _ in f) - 1

print(f"Rows: {row_count}")