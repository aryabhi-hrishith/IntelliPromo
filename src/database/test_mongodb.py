from pymongo import MongoClient

# Connect to local MongoDB
client = MongoClient("mongodb://localhost:27017/")

# Select project database
db = client["retail_promotion_planner"]

# Create/access collections
products = db["products"]
recommendations = db["recommendations"]

print("Database:", db.name)
print("Collections:", db.list_collection_names())

client.close()