import streamlit as st
import pandas as pd
import sqlite3

st.set_page_config(page_title="Services Manager", layout="wide")

# ---------- DB connection ----------
def get_connection():
    return sqlite3.connect("E:/SalonApp/salon.db", check_same_thread=False)

# ---------- Load Services ----------
def load_services(search_query=""):
    conn = get_connection()
    query = "SELECT * FROM Services"
    if search_query:
        query += " WHERE ServiceName LIKE ? OR Category LIKE ?"
        df = pd.read_sql(query, conn, params=(f"%{search_query}%", f"%{search_query}%"))
    else:
        df = pd.read_sql(query, conn)
    conn.close()
    return df

# ---------- Save updates ----------
def update_service(row):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE Services
        SET Category=?, ServiceName=?, Duration=?, Price_EUR=?, Active=?
        WHERE ServiceID=?
    """, (
        row["Category"],
        row["ServiceName"],
        row["Duration"],
        row["Price_EUR"],
        int(row["Active"]),
        row["ServiceID"]
    ))
    conn.commit()
    conn.close()

# ---------- Add new service ----------
def add_service(category, name, duration, price, active):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Services (Category, ServiceName, Duration, Price_EUR, Active)
        VALUES (?, ?, ?, ?, ?)
    """, (category, name, duration, price, int(active)))
    conn.commit()
    conn.close()

# ---------- UI ----------
st.title("💇‍♀️ Services Manager")

st.markdown("""
Manage your service catalog — update prices, durations, or toggle active/inactive services.  
Use the search bar to find services quickly.
""")

# Search bar
search = st.text_input("🔍 Search by service name or category")

# Load filtered services
services = load_services(search)

if services.empty:
    st.warning("No services found matching your search.")
else:
    st.write(f"Found {len(services)} services.")

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
        with st.spinner("Saving updates..."):
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
