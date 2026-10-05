from pymongo import MongoClient
import pandas as pd

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["retail_promotion_planner"]

# CSV files
products_file = "data/processed/promotion_inputs.csv"
recommendations_file = "data/processed/promotion_recommendations.csv"

# Read CSV files
print("Reading product data...")
products_df = pd.read_csv(products_file)

print("Reading recommendation data...")
recommendations_df = pd.read_csv(recommendations_file)

# Convert NaN to None for MongoDB
products_df = products_df.astype(object).where(pd.notna(products_df), None)
recommendations_df = recommendations_df.astype(object).where(
    pd.notna(recommendations_df), None
)

# Convert to dictionaries
products = products_df.to_dict("records")
recommendations = recommendations_df.to_dict("records")

# Clear old data so repeated runs don't create duplicates
db["products"].delete_many({})
db["recommendations"].delete_many({})

# Insert data
if products:
    db["products"].insert_many(products)

if recommendations:
    db["recommendations"].insert_many(recommendations)

print()
print("MongoDB import completed successfully!")
print("Products inserted:", db["products"].count_documents({}))
print("Recommendations inserted:", db["recommendations"].count_documents({}))

client.close()