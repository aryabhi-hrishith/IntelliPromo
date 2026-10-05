
import pandas as pd
from pathlib import Path

DATA_DIR = Path("data/synthetic")

files = [
    "products.csv",
    "customers.csv",
    "sales.csv",
    "inventory.csv"
]

for filename in files:
    path = DATA_DIR / filename

    if not path.exists():
        print(f"❌ Missing: {filename}")
        continue

    df = pd.read_csv(path)

    print(f"\n--- {filename} ---")
    print("Shape:", df.shape)
    print("Missing values:", df.isnull().sum().sum())
    print(df.head(3).to_string(index=False))

print("\nVerification complete.")