import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

# Set random seed for reproducibility
np.random.seed(42)

# Configuration for output directory
OUTPUT_DIR = "data/synthetic"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_data():
    # 1. Generate Products
    categories = ['Electronics', 'Clothing', 'Home & Kitchen', 'Beauty', 'Sports']
    products = pd.DataFrame({
        'product_id': range(1001, 1101),
        'product_name': [f"Product_{i}" for i in range(1, 101)],
        'category': np.random.choice(categories, 100),
        'selling_price': np.round(np.random.uniform(10, 500, 100), 2)
    })
    # Ensure cost is always lower than selling price
    products['cost_price'] = np.round(products['selling_price'] * np.random.uniform(0.4, 0.8, 100), 2)
    products.to_csv(f"{OUTPUT_DIR}/products.csv", index=False)

    # 2. Generate Customers
    customers = pd.DataFrame({
        'customer_id': range(5001, 5501),
        'region': np.random.choice(['North', 'South', 'East', 'West'], 500),
        'signup_date': [datetime(2022, 1, 1) + timedelta(days=np.random.randint(0, 730)) for _ in range(500)]
    })
    customers.to_csv(f"{OUTPUT_DIR}/customers.csv", index=False)

    # 3. Generate Sales
    # Using range indices to ensure references exist
    sales = pd.DataFrame({
        'transaction_id': range(10000, 20000),
        'customer_id': np.random.choice(customers['customer_id'], 10000),
        'product_id': np.random.choice(products['product_id'], 10000),
        'quantity': np.random.randint(1, 10, 10000),
        'transaction_date': [datetime(2023, 1, 1) + timedelta(days=np.random.randint(0, 365)) for _ in range(10000)],
        'discount_percentage': np.random.choice([0, 10, 20, 30, 40, 50], 10000)
    })
    sales.to_csv(f"{OUTPUT_DIR}/sales.csv", index=False)

    # 4. Generate Inventory
    inventory = pd.DataFrame({
        'product_id': products['product_id'],
        'available_stock': np.random.randint(0, 500, 100),
        'reorder_level': np.random.randint(20, 100, 100),
        'last_restock_date': [datetime(2023, 1, 1) + timedelta(days=np.random.randint(0, 365)) for _ in range(100)]
    })
    inventory.to_csv(f"{OUTPUT_DIR}/inventory.csv", index=False)

    # Print summary of generated data
    datasets = {
        "products.csv": products,
        "customers.csv": customers,
        "sales.csv": sales,
        "inventory.csv": inventory
    }

    for name, df in datasets.items():
        print(f"--- {name} ---")
        print(f"Rows: {len(df)}")
        print(f"Columns: {list(df.columns)}\n")

if __name__ == "__main__":
    generate_data()
    print("Data generation complete. Files saved to:", OUTPUT_DIR)