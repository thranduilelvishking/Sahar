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
