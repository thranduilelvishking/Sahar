'''import sqlite3

conn = sqlite3.connect("E:/SalonApp/salon.db")
cur = conn.cursor()

# 1️⃣ Rename the old table temporarily
cur.execute("ALTER TABLE Customers RENAME TO Customers_old;")

# 2️⃣ Create the new proper table structure
cur.execute("""
CREATE TABLE Customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    CustomerNo INTEGER UNIQUE,
    FullName TEXT NOT NULL,
    Phone TEXT,
    Email TEXT
);
""")

# 3️⃣ Copy existing data and generate CustomerNo if missing
cur.execute("""
INSERT INTO Customers (CustomerNo, FullName, Phone, Email)
SELECT CustomerNo, FullName, Phone, Email FROM Customers_old;
""")

# 4️⃣ Drop the old table
cur.execute("DROP TABLE Customers_old;")

conn.commit()
conn.close()

print("✅ Customers table successfully upgraded!")
'''
'''import sqlite3
import pandas as pd
conn = sqlite3.connect("E:/SalonApp/salon.db")
print(pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn))
conn.close()
'''
import sqlite3

conn = sqlite3.connect("E:/SalonApp/salon.db")
cur = conn.cursor()

# 1️⃣ Get all existing visits data
try:
    visits = cur.execute("SELECT * FROM Visits").fetchall()
    print(f"Exported {len(visits)} existing visits.")
except Exception as e:
    print("No existing visits found:", e)
    visits = []

# 2️⃣ Drop and recreate Visits table
cur.execute("DROP TABLE IF EXISTS Visits;")

cur.execute("""
CREATE TABLE Visits (
    VisitID INTEGER PRIMARY KEY AUTOINCREMENT,
    CustomerNo INTEGER,
    Date TEXT,
    Service TEXT,
    TotalPrice_Gross REAL,
    VAT REAL,
    NetIncome REAL,
    FOREIGN KEY (CustomerNo) REFERENCES Customers(CustomerNo)
);
""")

# 3️⃣ Reinsert previous data (if any)
if visits:
    for v in visits:
        cur.execute("""
            INSERT INTO Visits (VisitID, CustomerNo, Date, Service, TotalPrice_Gross, VAT, NetIncome)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, v)

conn.commit()
conn.close()
print("✅ Visits table recreated and linked properly to Customers.")
