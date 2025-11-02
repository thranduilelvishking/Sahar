import streamlit as st
import pandas as pd
from supabase import create_client, Client

st.set_page_config(page_title="💇‍♀️ Services Manager", layout="wide")

# --- DB Connection ---
@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_client()

# --- Load Services ---
def load_services(search_query=""):
    query = supabase.table("Services").select("*")
    if search_query:
        query = query.ilike("ServiceName", f"%{search_query}%") \
                     .or_().ilike("Category", f"%{search_query}%")
    res = query.execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# --- Update Service ---
def update_service(row):
    supabase.table("Services").update({
        "Category": row["Category"],
        "ServiceName": row["ServiceName"],
        "Duration": row["Duration"],
        "Price_EUR": row["Price_EUR"],
        "Active": row["Active"]
    }).eq("id", row["id"]).execute()

# --- Add New Service ---
def add_service(category, name, duration, price, active):
    supabase.table("Services").insert({
        "Category": category,
        "ServiceName": name,
        "Duration": duration,
        "Price_EUR": price,
        "Active": active
    }).execute()

# --- UI ---
st.title("💇‍♀️ Services Manager")

search = st.text_input("🔍 Search by service name or category")
services = load_services(search)

if services.empty:
    st.warning("No services found.")
else:
    st.write(f"Found {len(services)} services.")
    edited_df = st.data_editor(services, use_container_width=True, hide_index=True, key="editable_services")

    if st.button("💾 Save Changes"):
        pw = st.text_input("🔐 Enter admin password to confirm changes", type="password")
        if pw == st.secrets.get("app_password"):
            with st.spinner("Saving updates..."):
                for _, row in edited_df.iterrows():
                    update_service(row)
            st.success("✅ Changes saved successfully!")
        else:
            st.error("❌ Incorrect password — no changes saved.")

st.divider()
st.subheader("➕ Add New Service")

with st.form("add_service_form"):
    col1, col2, col3 = st.columns(3)
    category = col1.text_input("Category")
    name = col2.text_input("Service Name")
    duration = col3.number_input("Duration (min)", min_value=0.0, step=5.0)

    col4, col5 = st.columns(2)
    price = col4.number_input("Price (€)", min_value=0.0, step=1.0)
    active = col5.checkbox("Active", value=True)

    if st.form_submit_button("Add Service"):
        if not name.strip():
            st.error("Service Name cannot be empty.")
        else:
            add_service(category, name, duration, price, active)
            st.success(f"✅ Added new service: {name}")
            st.rerun()
