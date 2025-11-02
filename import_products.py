import sqlite3
import pandas as pd

# Load Excel/CSV file
df = pd.read_csv("E:/SalonApp/Products.csv")

# Clean column names (just in case)
df.columns = [c.strip().replace(" ", "_") for c in df.columns]

# Connect to database
conn = sqlite3.connect("E:/SalonApp/salon.db")

# Ensure Products table exists
conn.execute("""
CREATE TABLE IF NOT EXISTS Products (
    ProductName TEXT PRIMARY KEY,
    Brand TEXT,
    ColorNo TEXT,
    PackageWeight_g REAL,
    PackagePrice REAL,
    PricePerGram REAL,
    Quantity INTEGER
)
""")

# Write or replace products
df.to_sql("Products", conn, if_exists="replace", index=False)

conn.commit()
conn.close()

print(f"✅ Imported {len(df)} products into salon.db successfully!")
