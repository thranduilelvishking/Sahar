import streamlit as st
from supabase import create_client
import pandas as pd

# ---------------- PAGE SETUP ----------------
st.set_page_config(page_title="🌸 Customers", layout="wide")

# ---------------- SUPABASE CONNECTION ----------------
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

# ---------------- DATABASE FUNCTIONS ----------------
def get_customers():
    """Return all customers sorted by CustomerNo."""
    response = supabase.table("Customers").select("id, CustomerNo, FullName, Phone, Email").order("CustomerNo").execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def get_next_customer_no():
    """Return next available CustomerNo, starting from 7394 if empty."""
    response = supabase.table("Customers").select("CustomerNo").order("CustomerNo", desc=True).limit(1).execute()
    if not response.data:
        return 7394
    return response.data[0]["CustomerNo"] + 1

def add_customer(full_name, phone, email):
    """Add a new customer record."""
    next_no = get_next_customer_no()
    supabase.table("Customers").insert({
        "CustomerNo": next_no,
        "FullName": full_name,
        "Phone": phone,
        "Email": email
    }).execute()
    return next_no

def reset_customer_no(new_start):
    """Reset all customer numbers sequentially from new_start."""
    response = supabase.table("Customers").select("id").order("id").execute()
    current_no = new_start
    for item in response.data:
        supabase.table("Customers").update({"CustomerNo": current_no}).eq("id", item["id"]).execute()
        current_no += 1
    return new_start

# ---------------- UI ----------------
st.title("🌸 Salon Customers Dashboard")
st.markdown("Manage your clients — add, search, and view visit history easily.")

# Admin section
with st.expander("⚙️ Admin Controls"):
    st.caption("Reset the next Customer Number after testing.")
    current_next = get_next_customer_no()
    st.markdown(f"**Next available Customer #:** {current_next}")
    new_start = st.number_input("Set new starting CustomerNo", min_value=1, value=current_next, step=1)
    if st.button("💾 Update Starting Number"):
        reset_customer_no(new_start)
        st.success(f"✅ Customer numbering reset to start from {new_start}.")
        st.rerun()

st.divider()

# Add new customer
next_no = get_next_customer_no()
with st.expander("➕ Add New Customer"):
    st.markdown(f"**Next Customer #:** {next_no}")
    with st.form("add_customer_form"):
        full_name = st.text_input("Full Name")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        submitted = st.form_submit_button("Add Customer")
        if submitted:
            if not full_name.strip() or not phone.strip():
                st.error("Full name and phone number are required.")
            else:
                new_no = add_customer(full_name, phone, email)
                st.success(f"✅ Customer #{new_no} added successfully!")
                st.session_state["selected_customer_no"] = new_no
                st.switch_page("pages/2_Customer_Detail.py")

st.divider()

# Search
search_term = st.text_input("🔍 Search customers by name, phone, or email")

# Display customers
customers = get_customers()
if customers.empty:
    st.info("No customers found.")
else:
    if search_term:
        customers = customers[
            customers.apply(
                lambda x: search_term.lower() in str(x["FullName"]_
