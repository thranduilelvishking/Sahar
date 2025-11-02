import streamlit as st
import pandas as pd
from supabase import create_client

# ---------- CONFIG ----------
st.set_page_config(page_title="Products Inventory", page_icon="🌸", layout="wide")

# ---------- SUPABASE CONNECTION ----------
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# ---------- Load Products ----------
def load_products(search_query=""):
    query = supabase.table("Products").select("*")
    if search_query:
        # Manual filtering since Supabase text filters are exact match only
        res = query.execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df = df[
                df.apply(
                    lambda x: search_query.lower() in str(x["ProductName"]).lower()
                    or search_query.lower() in str(x["Brand"]).lower()
                    or search_query.lower() in str(x["ColorNo"]).lower(),
                    axis=1,
                )
            ]
        return df
    else:
        res = query.order("Brand", desc=False).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# ---------- Save updates ----------
def update_product(row):
    supabase.table("Products").update({
        "Brand": row["Brand"],
        "ColorNo": row["ColorNo"],
        "PackageWeight_g": row["PackageWeight_g"],
        "PackagePrice": row["PackagePrice"],
        "PricePerGram": row["PricePerGram"],
        "Quantity": row["Quantity"]
    }).eq("ProductName", row["ProductName"]).execute()

# ---------- UI ----------
st.title("🧴 Product Inventory Manager")

st.markdown("Easily manage your **product stock, pricing, and details** all in one place.")

# --- Search Bar ---
search = st.text_input("🔍 Search by product name, brand, or color number")

# --- Load and Display ---
products = load_products(search)

if products.empty:
    st.warning("No products found matching your search.")
else:
    st.write(f"**Found {len(products)} products.**")

    # Editable table
    edited_df = st.data_editor(
        products,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key="editable_products",
    )

    # Save changes
    if st.button("💾 Save Changes to Supabase"):
        with st.spinner("Saving updates..."):
            for _, row in edited_df.iterrows():
                update_product(row)
        st.success("✅ All changes saved successfully!")
