import streamlit as st
import pandas as pd
import uuid
from supabase import create_client, Client

st.set_page_config(page_title="🛍️ Retail Sales", layout="wide")

VAT_DEFAULT = 0.255  # 25.5% VAT
PROFIT_MARGIN = 0.5  # 50% profit

# ---------- Supabase ----------
@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_client()

# ---------- Session ----------
if "retail_session_id" not in st.session_state:
    st.session_state["retail_session_id"] = str(uuid.uuid4())
SESSION_ID = st.session_state["retail_session_id"]

# ---------- Database helpers ----------
def load_products(search=""):
    q = supabase.table("SaleProducts").select("*")
    if search:
        q = q.or_(f"Name.ilike.%{search}%,Brand.ilike.%{search}%")
    res = q.execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def save_product_row(row):
    supabase.table("SaleProducts").update({
        "Name": row["Name"],
        "Brand": row["Brand"],
        "BuyPriceEx": float(row["BuyPriceEx"]),
        "BuyPriceInc": float(row["BuyPriceInc"]),
        "SellPriceEx": float(row["SellPriceEx"]),
        "SellPriceInc": float(row["SellPriceInc"]),
        "ProfitAbs": float(row["ProfitAbs"]),
        "Quantity": float(row["Quantity"]),
        "VATRate": float(row["VATRate"])
    }).eq("id", row["id"]).execute()

def add_product(name, brand, buy_ex, qty):
    buy_inc = round(buy_ex * (1 + VAT_DEFAULT), 2)
    sell_ex = round(buy_ex * (1 + PROFIT_MARGIN), 2)
    sell_inc = round(sell_ex * (1 + VAT_DEFAULT), 2)
    profit_abs = round(buy_ex * PROFIT_MARGIN, 2)

    supabase.table("SaleProducts").insert({
        "Name": name,
        "Brand": brand,
        "BuyPriceEx": buy_ex,
        "BuyPriceInc": buy_inc,
        "SellPriceEx": sell_ex,
        "SellPriceInc": sell_inc,
        "ProfitAbs": profit_abs,
        "Quantity": qty,
        "VATRate": VAT_DEFAULT
    }).execute()

def add_to_cart(row, qty, discount):
    if qty <= 0:
        return "Quantity must be > 0"
    if qty > float(row["Quantity"]):
        return f"Not enough stock for {row['Name']}"

    unit_ex = row["SellPriceEx"] * (1 - discount / 100)
    unit_inc = unit_ex * (1 + row["VATRate"])
    line_ex = qty * unit_ex
    line_inc = qty * unit_inc

    supabase.table("SaleCart").insert({
        "SessionID": SESSION_ID,
        "ProductID": row["id"],
        "Name": row["Name"],
        "Brand": row["Brand"],
        "Qty": qty,
        "DiscountPct": discount,
        "VATRate": row["VATRate"],
        "UnitSellEx": unit_ex,
        "UnitSellInc": unit_inc,
        "LineTotalEx": line_ex,
        "LineTotalInc": line_inc
    }).execute()
    return None

def get_cart():
    res = supabase.table("SaleCart").select("*").eq("SessionID", SESSION_ID).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def clear_cart():
    supabase.table("SaleCart").delete().eq("SessionID", SESSION_ID).execute()

def confirm_sell(password):
    if password != st.secrets.get("app_password"):
        return "Incorrect password"
    cart = get_cart()
    if cart.empty:
        return "Cart is empty"

    for _, c in cart.iterrows():
        pid = int(c["ProductID"])
        qty = float(c["Qty"])
        prod = supabase.table("SaleProducts").select("Quantity").eq("id", pid).execute().data[0]
        stock = float(prod["Quantity"])
        if stock < qty:
            return f"Not enough stock for {c['Name']}"
        new_stock = round(stock - qty, 2)
        supabase.table("SaleProducts").update({"Quantity": new_stock}).eq("id", pid).execute()

    clear_cart()
    return None

# ---------- UI ----------
st.title("🛍️ Retail Sales Manager")

# --- Add to Inventory ---
st.subheader("➕ Add to Inventory")
with st.form("add_product"):
    c1, c2, c3, c4 = st.columns(4)
    name = c1.text_input("Product Name")
    brand = c2.text_input("Brand")
    buy_ex = c3.number_input("Buy Price (excl. VAT €)", min_value=0.0, step=0.1)
    qty = c4.number_input("Quantity", min_value=0.0, step=1.0)
    submit = st.form_submit_button("Add Product")

    if submit:
        if not name.strip():
            st.error("Name required.")
        else:
            add_product(name, brand, buy_ex, qty)
            st.success("✅ Product added successfully!")
            st.rerun()

st.divider()

# --- Product Table ---
search = st.text_input("🔍 Search products (name or brand)")
show_sensitive = st.toggle("👁 Show profit & buy prices", False)
edit_mode = st.toggle("✏️ Edit mode (full manual editing)", False)

df = load_products(search)
if df.empty:
    st.info("No products yet.")
else:
    if not edit_mode:
        df["BuyPriceInc"] = (df["BuyPriceEx"] * (1 + df["VATRate"])).round(2)
        df["SellPriceEx"] = (df["BuyPriceEx"] * (1 + PROFIT_MARGIN)).round(2)
        df["SellPriceInc"] = (df["SellPriceEx"] * (1 + df["VATRate"])).round(2)
        df["ProfitAbs"] = (df["BuyPriceEx"] * PROFIT_MARGIN).round(2)

    cols = ["Name", "Brand", "SellPriceEx", "SellPriceInc", "Quantity"]
    if show_sensitive:
        cols += ["BuyPriceEx", "BuyPriceInc", "ProfitAbs"]

    edited = st.data_editor(
        df[cols],
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        disabled=not edit_mode,
    )

    if edit_mode and st.button("💾 Save Edits"):
        pw = st.text_input("🔐 Enter admin password", type="password", key="pw_edit")
        if pw == st.secrets.get("app_password"):
            for _, row in edited.iterrows():
                rid = df.loc[df["Name"] == row["Name"]].iloc[0]["id"]
                save_product_row(pd.Series({
                    "id": rid,
                    "Name": row["Name"],
                    "Brand": row["Brand"],
                    "BuyPriceEx": row.get("BuyPriceEx", 0),
                    "BuyPriceInc": row.get("BuyPriceInc", 0),
                    "SellPriceEx": row.get("SellPriceEx", 0),
                    "SellPriceInc": row.get("SellPriceInc", 0),
                    "ProfitAbs": row.get("ProfitAbs", 0),
                    "Quantity": row["Quantity"],
                    "VATRate": VAT_DEFAULT
                }))
            st.success("✅ Changes saved.")
            st.rerun()
        else:
            st.error("❌ Incorrect password.")

# --- Cart Section ---
st.divider()
st.subheader("🧾 Shopping Cart")

cart = get_cart()
if cart.empty:
    st.info("Cart empty.")
else:
    cart["LineTotalEx"] = cart["Qty"] * cart["UnitSellEx"]
    cart["LineTotalInc"] = cart["Qty"] * cart["UnitSellInc"]
    st.dataframe(cart[["Name", "Brand", "Qty", "DiscountPct", "LineTotalEx", "LineTotalInc"]])
    total_ex = cart["LineTotalEx"].sum()
    total_inc = cart["LineTotalInc"].sum()
    st.markdown(f"**Total excl. VAT: €{total_ex:.2f}** | **Total incl. VAT: €{total_inc:.2f}**")

    pw = st.text_input("🔐 Password to confirm sale", type="password", key="pw_cart")
    if st.button("✅ Confirm Sale"):
        msg = confirm_sell(pw)
        if msg:
            st.error(msg)
        else:
            st.success("✅ Sale confirmed, inventory updated.")
            st.rerun()
