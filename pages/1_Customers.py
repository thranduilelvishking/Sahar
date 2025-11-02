import streamlit as st
import sqlite3
import pandas as pd

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Customers", layout="wide")

# ---------------- DATABASE FUNCTIONS ----------------
def get_connection():
    """Connect to the local salon database."""
    return sqlite3.connect("E:/SalonApp/salon.db", check_same_thread=False)

def get_customers():
    """Return all customers sorted by CustomerNo."""
    conn = get_connection()
    df = pd.read_sql("SELECT CustomerNo, FullName, Phone, Email FROM Customers ORDER BY CustomerNo ASC", conn)
    conn.close()
    return df

def get_next_customer_no():
    """Return the next available CustomerNo (starting from 7394 if empty)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(CustomerNo) FROM Customers")
    result = cursor.fetchone()
    conn.close()
    max_no = result[0] if result and result[0] else None
    return 7394 if max_no is None else max_no + 1

def add_customer(full_name, phone, email):
    """Add a new customer with auto-incrementing CustomerNo starting from 7394."""
    next_no = get_next_customer_no()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Customers (CustomerNo, FullName, Phone, Email)
        VALUES (?, ?, ?, ?)
    """, (next_no, full_name, phone, email))
    conn.commit()
    conn.close()
    return next_no

def reset_customer_no(new_start):
    """Reset the CustomerNo sequence by adjusting all records and starting from new_start."""
    conn = get_connection()
    cursor = conn.cursor()
    # Fetch all current records sorted by id
    cursor.execute("SELECT id FROM Customers ORDER BY id ASC")
    rows = cursor.fetchall()
    current_no = new_start
    for row in rows:
        cursor.execute("UPDATE Customers SET CustomerNo = ? WHERE id = ?", (current_no, row[0]))
        current_no += 1
    conn.commit()
    conn.close()
    return new_start

# ---------------- PAGE BODY ----------------
st.title("🌸 Salon Customers Dashboard")
st.markdown("Manage your clients — add, search, and view visit history easily.")

# --- Admin Section ---
with st.expander("⚙️ Admin Controls (for you only)"):
    st.markdown("Use this to **set or reset the next Customer Number** after testing.")
    current_next = get_next_customer_no()
    st.markdown(f"**Current Next Customer #:** {current_next}")
    new_start = st.number_input("Set new starting CustomerNo", min_value=1, value=current_next, step=1)
    if st.button("💾 Update Starting Number"):
        reset_customer_no(new_start)
        st.success(f"✅ Customer numbering reset to start from {new_start}.")
        st.rerun()

st.divider()

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
                st.write("")  # spacing
                if st.button("👁 View Details", key=f"view_{row['CustomerNo']}"):
                    st.session_state["selected_customer_no"] = row["CustomerNo"]
                    st.switch_page("pages/2_Customer_Detail.py")
