import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Salon Manager", page_icon="🌸", layout="wide")

st.title("🌸 Salon Manager Dashboard")

st.markdown("""
Welcome to **Salon Manager** — your all-in-one beauty business tool! 💇‍♀️  

Use the sidebar or tabs to:
- Manage **customers** 🌸  
- Track **visits** and **products used** 💅  
- Update your **services** and **inventory** 🧴  
""")

# --- Connect to Supabase ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)

    # Test connection
    res = supabase.table("Customers").select("count(*)").execute()
    st.success("✅ Connected to Supabase database successfully!")

    # Show available tables
    st.subheader("📋 Available Tables in Database")
    tables = ["Customers", "Visits", "ProductsUsed", "Products", "Services", "SaleProducts"]
    st.dataframe(pd.DataFrame({"Table Name": tables}))

except Exception as e:
    st.error(f"❌ Failed to connect to Supabase: {e}")
