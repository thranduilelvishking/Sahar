import streamlit as st
import pandas as pd
from supabase import create_client

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Customers", page_icon="🌸", layout="wide")

# ---------------- SUPABASE CONNECTION ----------------
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# ---------------- DATABASE FUNCTIONS ----------------
def get_customers():
    """Return all customers sorted by CustomerNo."""
    res = supabase.table("Customers").select("CustomerNo, FullName, Phone, Email").order("CustomerNo", desc=False).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=["CustomerNo", "FullName", "Phone", "Email"])

def get_next_customer_no():
    """Return the next available CustomerNo (starting from 7394 if empty)."""
    res = supabase.table("Customers").select("CustomerNo").order("CustomerNo", desc=True).limit(1).execute()
    if res.data and res.data[0]["CustomerNo"]:
        return int(res.data[0]["CustomerNo"]) + 1
    else:
        return 7394

def add_customer(full_name, phone, email):
    """Add a new customer with auto-incrementing CustomerNo starting from 7394."""
    next_no = get_next_customer_no()
    supabase.table("Customers").insert({
        "CustomerNo": next_no,
        "FullName": full_name,
        "Phone": phone,
        "Email": email
    }).execute()
    return next_no

def reset_customer_no(new_start):
    """Reset customer numbering logic by offset (soft reset, does not modify DB)."""
    st.session_state["manual_next_no"] = new_start
    return new_start

# ---------------- PAGE BODY ----------------
st.title("🌸 Salon Customers Dashboard")
st.markdown("Manage your clients — add, search, and view visit history easily.")

# --- Admin Section ---
with st.expander("⚙️ Admin Controls (for you only)"):
    st.markdown("Use this to **set or reset the next Customer Number** after testing.")
    current_next = get_next_customer_no()
    st.markdown(f"**Current Next Customer #:** {current_next}")
    new_start = st.number_input("Set new starting CustomerNo", min_value=1000, value=current_next, step=1)
    if st.button("💾 Update Starting Number"):
        reset_customer_no(new_start)
        st.success(f"✅ Customer numbering reset to start from {new_start}.")
        st.rerun()

st.divider()

# --- Add New Customer ---
next_no = st.session_state.get("manual_next_no", get_next_customer_no())
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
                new_no = add_customer(full_name.strip(), phone.strip(), email.strip())
                st.success(f"✅ Customer #{new_no} added successfully!")
                if "manual_next_no" in st.session_state:
                    st.session_state["manual_next_no"] += 1
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
                st.write("")
                st.write("")
                if st.button("👁 View Details", key=f"view_{row['CustomerNo']}"):
                    st.query_params["customer_no"] = row["CustomerNo"]
                    st.switch_page("pages/2_Customer_Detail.py")
