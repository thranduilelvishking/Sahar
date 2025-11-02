import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Customers", layout="wide")

# ---------------- SUPABASE CONNECTION ----------------
@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_connection()

# ---------------- DATABASE FUNCTIONS ----------------
def get_customers():
    res = supabase.table("Customers").select("CustomerNo, FullName, Phone, Email").order("CustomerNo").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def get_next_customer_no():
    res = supabase.table("Customers").select("CustomerNo").order("CustomerNo", desc=True).limit(1).execute()
    if res.data and res.data[0].get("CustomerNo"):
        return int(res.data[0]["CustomerNo"]) + 1
    return 7394

def add_customer(full_name, phone, email):
    next_no = get_next_customer_no()
    supabase.table("Customers").insert({
        "CustomerNo": next_no,
        "FullName": full_name,
        "Phone": phone,
        "Email": email
    }).execute()
    return next_no

# ---------------- PAGE BODY ----------------
st.title("🌸 Salon Customers Dashboard")
st.markdown("Manage your clients — add, search, and view visit history easily.")

# --- Add New Customer ---
next_no = get_next_customer_no()
with st.expander("➕ Add New Customer"):
    st.markdown(f"**Next Customer #:** {next_no}")
    with st.form("add_customer_form"):
        full_name = st.text_input("Full Name")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        submitted = st.form_submit_button("Add Customer")

        if submitted:
            if full_name.strip() == "" or phone.strip() == "":
                st.error("Full name and phone number are required.")
            else:
                new_no = add_customer(full_name, phone, email)
                st.success(f"✅ Customer #{new_no} added successfully!")
                st.rerun()

st.divider()

# --- Search Bar ---
search_term = st.text_input("🔍 Search customers by name, phone, or email")

# --- Customer List ---
customers = get_customers()

if customers.empty:
    st.info("No customers in the database yet.")
else:
    # Filter dynamically
    if search_term:
        customers = customers[
            customers.apply(
                lambda x: search_term.lower() in str(x["FullName"]).lower()
                or search_term.lower() in str(x["Phone"]).lower()
                or search_term.lower() in str(x["Email"]).lower(),
                axis=1,
            )
        ]

    st.markdown(f"**Total customers:** {len(customers)}")

    # --- Display customers in cards ---
    for _, row in customers.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### 🌸 {row['FullName']}")
                st.write(f"**Customer #:** {row['CustomerNo']}")
                st.write(f"📞 {row['Phone']}")
                if row['Email']:
                    st.write(f"✉️ {row['Email']}")
            with col2:
                st.write("")  # spacing
                if st.button(f"👁 View", key=f"view_{row['CustomerNo']}"):
                    st.session_state["selected_customer_no"] = row["CustomerNo"]
                    st.query_params.update({"customer_no": row["CustomerNo"]})
                    st.switch_page("pages/2_Customer_Detail.py")
