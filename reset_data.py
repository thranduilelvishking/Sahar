from supabase import create_client
import streamlit as st

# --- Supabase connection (same as app) ---
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase = create_client(url, key)

tables_to_clean = ["ProductsUsed", "Visits", "Customers"]

for t in tables_to_clean:
    print(f"Cleaning table {t}...")
    supabase.table(t).delete().neq("CustomerNo", 0).execute()

print("✅ All test data cleared successfully!")
