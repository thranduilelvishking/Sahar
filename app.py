import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Salon Manager", page_icon="🌸", layout="wide")
# ---- Simple password protection ----
PASSWORD = st.secrets.get("app_password", None)

if PASSWORD:
    pw = st.text_input("🔐 Enter password to access Salon Manager", type="password")
    if pw != PASSWORD:
        st.warning("Please enter the correct password.")
        st.stop()
else:
    st.error("Admin password not found in secrets. Add 'app_password' to Streamlit secrets.")
    st.stop()

st.title("🌸 Salon Manager Dashboard")

st.markdown("""
Welcome to **Salon Manager (Cloud)** 💇‍♀️

Use the sidebar / pages to:
- Manage customers 🌸  
- Track visits and products used 💅  
- Update services and inventory 🧴  
""")

# --- Connect to Supabase ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)

    # Instead of count(*), just try a light select
    test_res = supabase.table("Customers").select("*").limit(1).execute()

    st.success("✅ Connected to Supabase successfully!")

    # Show cloud tables we expect to use
    st.subheader("📋 Available Tables")
    tables = [
        "Customers",
        "Visits",
        "ProductsUsed",
        "Products",
        "Services",
        "SaleProducts",
    ]
    st.dataframe(pd.DataFrame({"Table Name": tables}))

    # Extra debug info (optional: shows if Customers table has any rows yet)
    if test_res.data:
        st.info(f"Customers table OK. Example customer: {test_res.data[0].get('FullName', '(no name)')}")
    else:
        st.info("Customers table OK but currently has 0 rows.")

except Exception as e:
    st.error(f"❌ Failed to connect to Supabase: {e}")

