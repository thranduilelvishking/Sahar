import streamlit as st
import pandas as pd
from supabase import create_client

# ---------- CONFIG ----------
st.set_page_config(page_title="Services Manager", page_icon="🌸", layout="wide")

# ---------- SUPABASE CONNECTION ----------
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# ---------- Load Services ----------
def load_services(search_query=""):
    res = supabase.table("Services").select("*").execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    if not df.empty and search_query:
        df = df[
            df.apply(
                lambda x: search_query.lower() in str(x["ServiceName"]).lower()
                or search_query.lower() in str(x["Category"]).lower(),
                axis=1,
            )
        ]
    return df

# ---------- Save updates ----------
def update_service(row):
    supabase.table("Services").update({
        "Category": row["Category"],
        "ServiceName": row["ServiceName"],
        "Duration": row["Duration"],
        "Price_EUR": row["Price_EUR"],
        "Active": bool(row["Active"])
    }).eq("ServiceID", row["ServiceID"]).execute()

# ---------- Add new service ----------
def add_service(category, name, duration, price, active):
    supabase.table("Services").insert({
        "Category": category,
        "ServiceName": name,
        "Duration": duration,
        "Price_EUR": price,
        "Active": bool(active)
    }).execute()

# ---------- UI ----------
st.title("💇‍♀️ Services Manager")

st.markdown("""
Manage your service catalog — update prices, durations, or toggle active/inactive services.  
Use the search bar to find services quickly.
""")

# --- Search Bar ---
search = st.text_input("🔍 Search by service name or category")

# --- Load Services ---
services = load_services(search)

if services.empty:
    st.warning("No services found matching your search.")
else:
    st.write(f"**Found {len(services)} services.**")

    # Editable table
    edited_df = st.data_editor(
        services,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key="editable_services",
    )

    # Save button
    if st.button("💾 Save Changes"):
        with st.spinner("Saving updates to Supabase..."):
            for _, row in edited_df.iterrows():
                update_service(row)
        st.success("✅ All service updates saved successfully!")

# ---------- Add new service form ----------
st.divider()
st.subheader("➕ Add New Service")

with st.form("add_service_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        category = st.text_input("Category")
    with col2:
        name = st.text_input("Service Name")
    with col3:
        duration = st.number_input("Duration (min)", min_value=0.0, step=5.0)
    
    col4, col5 = st.columns(2)
    with col4:
        price = st.number_input("Price (€)", min_value=0.0, step=1.0)
    with col5:
        active = st.checkbox("Active", value=True)

    submitted = st.form_submit_button("Add Service")

    if submitted:
        if not name.strip():
            st.error("Service Name cannot be empty.")
        else:
            add_service(category, name, duration, price, active)
            st.success(f"✅ Added new service: {name}")
            st.rerun()
