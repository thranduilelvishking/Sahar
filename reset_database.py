import sqlite3

DB_PATH = "E:/SalonApp/salon.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Enable foreign key checks
cur.execute("PRAGMA foreign_keys = ON;")

# List all relevant tables
tables = ["Customers", "Visits", "ProductsUsed", "SaleProducts"]

# Clear all data safely
for t in tables:
    try:
        cur.execute(f"DELETE FROM {t};")
        print(f"✅ Cleared table: {t}")
    except Exception as e:
        print(f"⚠️ Could not clear {t}: {e}")

# Reset SQLite’s internal autoincrement counters
cur.execute("DELETE FROM sqlite_sequence;")

# Reset Customer numbering manually to start from 7394
try:
    cur.execute("""
        UPDATE sqlite_sequence SET seq = 7393 WHERE name = 'Customers';
    """)
    print("✅ Reset next CustomerNo start to 7394.")
except Exception as e:
    print("⚠️ Could not reset CustomerNo counter:", e)

conn.commit()
conn.close()

print("\n🌸 Salon database cleaned and ready for fresh use!")
