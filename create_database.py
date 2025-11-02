import sqlite3

def create_database():
    conn = sqlite3.connect("salon.db")
    cursor = conn.cursor()

    # --- Customers Table ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Customers (
        CustomerNo INTEGER PRIMARY KEY AUTOINCREMENT,
        FullName TEXT NOT NULL,
        Phone TEXT,
        Email TEXT
    );
    """)

    # --- Visits Table ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Visits (
        VisitID INTEGER PRIMARY KEY AUTOINCREMENT,
        CustomerNo INTEGER NOT NULL,
        Date TEXT,
        Service TEXT,
        TotalPrice_Gross REAL,
        VAT REAL,
        NetIncome REAL,
        FOREIGN KEY (CustomerNo) REFERENCES Customers(CustomerNo)
    );
    """)

    # --- ProductsUsed Table ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ProductsUsed (
        UsedID INTEGER PRIMARY KEY AUTOINCREMENT,
        VisitID INTEGER NOT NULL,
        Product TEXT,
        Brand TEXT,
        ColorNo TEXT,
        WeightUsed_g REAL,
        ProductCost REAL,
        FOREIGN KEY (VisitID) REFERENCES Visits(VisitID)
    );
    """)

    # --- Products Table (for salon use) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Products (
        ProductID INTEGER PRIMARY KEY AUTOINCREMENT,
        ProductName TEXT NOT NULL,
        Brand TEXT,
        ColorNo TEXT,
        PackageWeight_g REAL,
        PackagePrice REAL,
        PricePerGram REAL,
        Quantity INTEGER
    );
    """)

    # --- SaleProducts Table (for resale goods) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS SaleProducts (
        SaleProductID INTEGER PRIMARY KEY AUTOINCREMENT,
        ProductName TEXT NOT NULL,
        Brand TEXT,
        Category TEXT,
        UnitPrice REAL,
        Quantity INTEGER,
        Active BOOLEAN DEFAULT 1
    );
    """)

    # --- Services Table ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Services (
        ServiceID INTEGER PRIMARY KEY AUTOINCREMENT,
        Category TEXT,
        ServiceName TEXT,
        Duration TEXT,
        Price_EUR REAL,
        Active BOOLEAN DEFAULT 1
    );
    """)

    conn.commit()
    conn.close()
    print("✅ salon.db created successfully with all tables!")

if __name__ == "__main__":
    create_database()
