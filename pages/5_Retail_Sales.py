import streamlit as st
import pandas as pd
import uuid
from supabase import create_client, Client

st.set_page_config(page_title="🛍️ Retail Sales", layout="wide")

# ---------- Constants ----------
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
        "Quantity": qty
    }).execute()

def add_to_cart(row, qty):
    qty = float(qty)
    if qty <= 0:
        return "Quantity must be > 0"
    if qty > float(row["Quantity"]):
        return f"Not enough stock for {row['Name']}"

    line_ex = round(row["SellPriceEx"] * qty, 2)
    line_inc = round(row["SellPriceInc"] * qty, 2)

    # Check if already in cart -> update qty instead of duplicate
    existing = supabase.table("SaleCart").select("id,Qty").eq("SessionID", SESSION_ID).eq("ProductID", row["id"]).execute()
    if existing.data:
        current = float(existing.data[0]["Qty"])
        new_qty = current + qty
        supabase.table("SaleCart").update({
            "Qty": new_qty,
            "LineTotalEx": round(row["SellPriceEx"] * new_qty, 2),
            "LineTotalInc": round(row["SellPriceInc"] * new_qty, 2)
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        supabase.table("SaleCart").insert({
            "SessionID": SESSION_ID,
            "ProductID": row["id"],
            "Name": row["Name"],
            "Brand": row["Brand"],
            "Qty": qty,
            "UnitSellEx": row["SellPriceEx"],
            "UnitSellInc": row["SellPriceInc"],
            "LineTotalEx": line_ex,
            "LineTotalInc": line_inc
        }).execute()
    return None

def get_cart():
    res = supabase.table("SaleCart").select("*").eq("SessionID", SESSION_ID).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def update_cart_quantity(cart_id, new_qty):
    try:
        item = supabase.table("SaleCart").select("UnitSellEx,UnitSellInc").eq("id", cart_id).execute().data[0]
        new_qty = float(new_qty)
        line_ex = round(item["UnitSellEx"] * new_qty, 2)
        line_inc = round(item["UnitSellInc"] * new_qty, 2)
        supabase.table("SaleCart").update({
            "Qty": new_qty,
            "LineTotalEx": line_ex,
            "LineTotalInc": line_inc
        }).eq("id", cart_id).execute()
    except Exception as e:
        st.error(f"Error updating cart: {e}")

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

# --- Product Table with Add to Cart ---
search = st.text_input("🔍 Search products (name or brand)")
df = load_products(search)
if df.empty:
    st.info("No products yet.")
else:
    st.subheader("📦 Inventory")
    df["BuyPriceInc"] = (df["BuyPriceEx"] * (1 + VAT_DEFAULT)).round(2)
    df["SellPriceEx"] = (df["BuyPriceEx"] * (1 + PROFIT_MARGIN)).round(2)
    df["SellPriceInc"] = (df["SellPriceEx"] * (1 + VAT_DEFAULT)).round(2)
    df["ProfitAbs"] = (df["BuyPriceEx"] * PROFIT_MARGIN).round(2)

    for idx, row in df.iterrows():
        c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 2, 1])
        c1.markdown(f"**{row['Name']}**  \n{row['Brand']}")
        c2.markdown(f"€{row['SellPriceEx']:.2f} excl. VAT")
        c3.markdown(f"€{row['SellPriceInc']:.2f} incl. VAT")
        c4.markdown(f"Stock: {row['Quantity']}")
        qty_input = c5.number_input(f"Qty_{idx}", min_value=0.0, max_value=float(row["Quantity"]), step=1.0, label_visibility="collapsed")
        if c6.button("🛒", key=f"addcart_{idx}"):
            msg = add_to_cart(row, qty_input)
            if msg:
                st.error(msg)
            else:
                st.success(f"Added {qty_input} × {row['Name']}")
                st.rerun()

st.divider()

# --- Shopping Cart Section ---
st.subheader("🧾 Shopping Cart")
cart = get_cart()
if cart.empty:
    st.info("Cart empty.")
else:
    total_ex = cart["LineTotalEx"].sum()
    total_inc = cart["LineTotalInc"].sum()
    vat_total = round(total_inc - total_ex, 2)

    for idx, c in cart.iterrows():
        c1, c2, c3, c4, c5, c6, c7 = st.columns([3, 2, 2, 2, 2, 1, 1])
        c1.markdown(f"**{c['Name']}**  \n{c['Brand']}")
        c2.markdown(f"€{c['UnitSellEx']:.2f}")
        c3.markdown(f"€{c['UnitSellInc']:.2f}")
        c4.markdown(f"€{c['LineTotalEx']:.2f}")
        c5.markdown(f"€{c['LineTotalInc']:.2f}")
        # quantity controls
        dec = c6.button("➖", key=f"dec_{idx}")
        inc = c7.button("➕", key=f"inc_{idx}")
        if dec and c["Qty"] > 1:
            update_cart_quantity(c["id"], c["Qty"] - 1)
            st.rerun()
        elif inc:
            update_cart_quantity(c["id"], c["Qty"] + 1)
            st.rerun()
        c1.caption(f"Qty: {c['Qty']}")

    st.markdown("---")
    st.markdown(f"**🧮 Totals**")
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Items in Cart", len(cart))
    t2.metric("Total excl. VAT (€)", f"{total_ex:.2f}")
    t3.metric("VAT (€)", f"{vat_total:.2f}")
    t4.metric("Total incl. VAT (€)", f"{total_inc:.2f}")

    st.markdown("---")
    pw = st.text_input("🔐 Password to confirm sale", type="password", key="pw_cart")
    if st.button("✅ Confirm Sale"):
        msg = confirm_sell(pw)
        if msg:
            st.error(msg)
        else:
            st.success("✅ Sale confirmed and inventory updated.")
            st.rerun()
