import pandas as pd

excel_path = "E:/SalonApp/SalonManager.xlsm"
output_path = "E:/SalonApp/Services.csv"

# Load only the 'Services' sheet
df = pd.read_excel(excel_path, sheet_name="Services", header=0)

# Drop all-empty rows and columns
df = df.dropna(how="all").dropna(axis=1, how="all")

# Preview result
print("Columns found:", list(df.columns))
print(df.head())

# Save cleaned data to CSV
df.to_csv(output_path, index=False)
print(f"✅ Exported clean 'Services' sheet to {output_path}")
