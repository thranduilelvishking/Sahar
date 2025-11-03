import streamlit as st
import pandas as pd
from supabase import create_client, Client

st.set_page_config(page_title="🧴 Product Inventory", layout="wide")

# --- DB Connection ---
@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_client()

# --- Load Products ---
def load_products(search_query=""):
    query = supabase.table("Products").select("*")
    if search_query.strip():
        # Combine OR conditions into one string (correct syntax)
        query = query.or_(
            f"ProductName.ilike.%{search_query}%,"
            f"Brand.ilike.%{search_query}%,"
            f"ColorNo.ilike.%{search_query}%"
        )
    res = query.execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# --- Update Product ---
def update_product(row):
    supabase.table("Products").update({
        "Brand": row["Brand"],
        "ColorNo": row["ColorNo"],
        "PackageWeight_g": row["PackageWeight_g"],
        "PackagePrice": row["PackagePrice"],
        "PricePerGram": row["PricePerGram"],
        "Quantity": row["Quantity"]
    }).eq("id", row["id"]).execute()

# --- UI ---
st.title("🧴 Product Inventory Manager")

search = st.text_input("🔍 Search by product name, brand, or color number")
products = load_products(search)

if products.empty:
    st.warning("No products found.")
else:
    st.write(f"Found {len(products)} products.")
    edited_df = st.data_editor(
        products,
        use_container_width=True,
        hide_index=True,
        key="editable_products"
    )

    if st.button("💾 Save Changes"):
        pw = st.text_input("🔐 Enter admin password to confirm changes", type="password")
        if pw == st.secrets.get("app_password"):
            with st.spinner("Saving updates..."):
                for _, row in edited_df.iterrows():
                    update_product(row)
            st.success("✅ Changes saved successfully!")
        else:
            st.error("❌ Incorrect password — no changes saved.")
