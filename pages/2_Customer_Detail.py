import streamlit as st
import pandas as pd
import sqlite3
from datetime import date

st.set_page_config(page_title="Customer Detail", layout="wide")

# ---------- DB CONNECTION ----------
def get_connection():
    return sqlite3.connect("E:/SalonApp/salon.db", check_same_thread=False)

# ---------- DATA HELPERS ----------
def get_customer(customer_no):
    conn = get_connection()
    query = "SELECT * FROM Customers WHERE CustomerNo = ?"
    df = pd.read_sql(query, conn, params=(customer_no,))
    conn.close()
    return df.iloc[0] if not df.empty else None

def get_visits(customer_no):
    conn = get_connection()
    query = "SELECT * FROM Visits WHERE CustomerNo = ? ORDER BY Date DESC"
    df = pd.read_sql(query, conn, params=(customer_no,))
    conn.close()
    return df

def get_products_used(visit_id):
    conn = get_connection()
    query = "SELECT * FROM ProductsUsed WHERE VisitID = ?"
    df = pd.read_sql(query, conn, params=(visit_id,))
    conn.close()
    return df

def get_products_list():
    conn = get_connection()
    df = pd.read_sql("SELECT ProductName, Brand, ColorNo, PricePerGram FROM Products ORDER BY Brand, ProductName", conn)
    conn.close()
    return df

def add_visit(customer_no, visit_date, service, total_price):
    conn = get_connection()
    cursor = conn.cursor()
    vat = round(total_price * 0.255, 2)
    net = round(total_price - vat - 2, 2)  # misc cost = 2 €
    cursor.execute(
        "INSERT INTO Visits (CustomerNo, Date, Service, TotalPrice_Gross, VAT, NetIncome) VALUES (?, ?, ?, ?, ?, ?)",
        (customer_no, visit_date, service, total_price, vat, net)
    )
    conn.commit()
    conn.close()

def add_product_used(visit_id, product_name, weight_used):
    conn = get_connection()

    # Fetch product info
    pinfo = pd.read_sql(
        "SELECT Brand, ColorNo, PricePerGram FROM Products WHERE ProductName = ?",
        conn, params=(product_name,)
    )
    if not pinfo.empty:
        brand = pinfo.iloc[0]["Brand"]
        color = pinfo.iloc[0]["ColorNo"]
        price_per_g = pinfo.iloc[0]["PricePerGram"]
        cost = round(weight_used * price_per_g, 2)
    else:
        brand, color, cost = None, None, 0.0

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ProductsUsed (VisitID, Product, Brand, ColorNo, WeightUsed_g, ProductCost)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (visit_id, product_name, brand, color, weight_used, cost))

    # update net income in visits after adding a product
    cursor.execute("""
        UPDATE Visits
        SET NetIncome = TotalPrice_Gross - VAT - (
            SELECT IFNULL(SUM(ProductCost), 0) + 2 FROM ProductsUsed WHERE VisitID = ?
        )
        WHERE VisitID = ?
    """, (visit_id, visit_id))

    conn.commit()
    conn.close()

# ---------- PAGE BODY ----------
st.title("💇‍♀️ Customer Detail")

customer_no = st.session_state.get("selected_customer_no")


if not customer_no:
    st.warning("No customer selected. Please go back to the Customers page.")
    st.stop()

customer = get_customer(customer_no)
if customer is None:
    st.error(f"No customer found with number {customer_no}.")
    st.stop()

st.header(f"{customer['FullName']} (#{customer['CustomerNo']})")
st.write(f"📞 {customer['Phone']} | ✉️ {customer['Email']}")
if st.button("🔙 Back to Customers"):
    st.switch_page("pages/1_Customers.py")


st.divider()

# ---------- VISITS ----------
st.subheader("💈 Visits")

visits = get_visits(customer_no)
st.dataframe(visits, use_container_width=True)

with st.expander("➕ Add New Visit"):
    with st.form("add_visit_form"):
        visit_date = st.date_input("Visit Date", date.today())
        service = st.text_input("Service")
        total_price = st.number_input("Total Price (€)", min_value=0.0, step=0.5)
        submitted = st.form_submit_button("Add Visit")
        if submitted:
            add_visit(customer_no, str(visit_date), service, total_price)
            st.success("✅ Visit added successfully!")
            st.rerun()

st.divider()

# ---------- PRODUCTS USED ----------
st.subheader("🧴 Products Used")

if not visits.empty:
    # choose which visit to add product to
    visit_options = {
        f"{v['Date']} – {v['Service']} (ID {v['VisitID']})": v['VisitID']
        for _, v in visits.iterrows()
    }
    selected_visit_label = st.selectbox("Select Visit", list(visit_options.keys()))
    selected_visit_id = visit_options[selected_visit_label]

    products_used = get_products_used(selected_visit_id)
    st.dataframe(products_used, use_container_width=True)

    # ---------- ADD PRODUCT SECTION ----------
    with st.expander("➕ Add Product Used"):
        products_df = get_products_list()

        # 🔍 Real-time search
        search_term = st.text_input("Search by name, brand, or color number")

        if search_term:
            filtered_df = products_df[
                products_df.apply(
                    lambda x: search_term.lower() in str(x["ProductName"]).lower()
                    or search_term.lower() in str(x["Brand"]).lower()
                    or search_term.lower() in str(x["ColorNo"]).lower(),
                    axis=1,
                )
            ]
        else:
            filtered_df = products_df

        if filtered_df.empty:
            st.warning("No matching products found.")
        else:
            product_names = filtered_df["ProductName"].tolist()

            with st.form("add_product_form"):
                selected_product = st.selectbox("Select Product", product_names)
                pinfo = filtered_df.loc[filtered_df["ProductName"] == selected_product].iloc[0]
                st.markdown(
                    f"""
                    **Brand:** {pinfo['Brand']}  
                    **ColorNo:** {pinfo['ColorNo']}  
                    **Price per g:** {pinfo['PricePerGram']} €
                    """
                )

                weight_used = st.number_input("Weight Used (g)", min_value=0.0, step=0.5)

                if st.form_submit_button("Add Product"):
                    add_product_used(selected_visit_id, selected_product, weight_used)
                    st.success(f"✅ Added {selected_product} to Visit {selected_visit_id}")
                    st.rerun()
else:
    st.info("No visits yet. Add one above to record product usage.")
