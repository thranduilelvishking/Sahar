import streamlit as st
import pandas as pd
import sqlite3

st.set_page_config(page_title="Products Inventory", layout="wide")

# ---------- DB connection ----------
def get_connection():
    return sqlite3.connect("E:/SalonApp/salon.db", check_same_thread=False)

# ---------- Load Products ----------
def load_products(search_query=""):
    conn = get_connection()
    query = "SELECT * FROM Products"
    if search_query:
        query += " WHERE ProductName LIKE ? OR Brand LIKE ? OR ColorNo LIKE ?"
        df = pd.read_sql(query, conn, params=(f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
    else:
        df = pd.read_sql(query, conn)
    conn.close()
    return df

# ---------- Save updates ----------
def update_product(row):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE Products
        SET Brand=?, ColorNo=?, PackageWeight_g=?, PackagePrice=?, PricePerGram=?, Quantity=?
        WHERE ProductName=?
    """, (
        row["Brand"],
        row["ColorNo"],
        row["PackageWeight_g"],
        row["PackagePrice"],
        row["PricePerGram"],
        row["Quantity"],
        row["ProductName"]
    ))
    conn.commit()
    conn.close()

# ---------- UI ----------
st.title("🧴 Product Inventory Manager")


# Search bar
search = st.text_input("🔍 Search by product name, brand, or color number")

# Load filtered products
products = load_products(search)

if products.empty:
    st.warning("No products found matching your search.")
else:
    st.write(f"Found {len(products)} products.")

    # Editable table
    edited_df = st.data_editor(
        products,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key="editable_products",
    )

    # Save button
    if st.button("💾 Save Changes to Database"):
        with st.spinner("Saving updates..."):
            for _, row in edited_df.iterrows():
                update_product(row)
        st.success("✅ All changes saved successfully!")


