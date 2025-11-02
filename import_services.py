import sqlite3
import pandas as pd

# Load the exported Services CSV
df = pd.read_csv("E:/SalonApp/Services.csv")

# Clean up column names just in case
df.columns = [c.strip().replace(" ", "_") for c in df.columns]

# Connect to the database
conn = sqlite3.connect("E:/SalonApp/salon.db")

# Ensure the Services table exists
conn.execute("""
CREATE TABLE IF NOT EXISTS Services (
    ServiceID INTEGER PRIMARY KEY AUTOINCREMENT,
    Category TEXT,
    ServiceName TEXT UNIQUE,
    Duration REAL,
    Price_EUR REAL,
    Active INTEGER
)
""")

# Insert or replace data
df.to_sql("Services", conn, if_exists="replace", index=False)

conn.commit()
conn.close()

print(f"✅ Imported {len(df)} services into salon.db successfully!")
