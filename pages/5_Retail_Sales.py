import streamlit as st
import pandas as pd
import uuid
from supabase import create_client, Client

st.set_page_config(page_title="🛍️ Retail Sales", layout="wide")

VAT_DEFAULT = 0.255   # 25.5% VAT (constant, not stored in SaleProducts)
PROFIT_MARGIN = 0.5   # 50% profit on buy price (excl. VAT)

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
def load_products(search: str = "") -> pd.DataFrame:
    q = supabase.table("SaleProducts").select("*")
    if search:
        # Search by Name OR Brand
        q = q.or_(f"Name.ilike.%{search}%,Brand.ilike.%{search}%")
    res = q.execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def save_product_row(row: pd.Series) -> None:
    # Persist only the columns that exist in SaleProducts
    payload = {
        "Name": str(row["Name"]).strip(),
        "Brand": str(row["Brand"]).strip() if pd.notna(row.get("Brand")) else None,
        "BuyPriceEx": float(row.get("BuyPriceEx", 0) or 0),
        "BuyPriceInc": float(row.get("BuyPriceInc", 0) or 0),
        "SellPriceEx": float(row.get("SellPriceEx", 0) or 0),
        "SellPriceInc": float(row.get("SellPriceInc", 0) or 0),
        "ProfitAbs": float(row.get("ProfitAbs", 0) or 0),
        "Quantity": float(row.get("Quantity", 0) or 0),
    }
    try:
        supabase.table("SaleProducts").update(payload).eq("id", row["id"]).execute()
    except Exception as e:
        st.exception(e)

def add_product(name: str, brand: str, buy_ex: float, qty: float) -> None:
    buy_ex = float(buy_ex)
    qty = float(qty)

    # Auto-calculations based on constants
    buy_inc = round(buy_ex * (1 + VAT_DEFAULT), 2)
    sell_ex = round(buy_ex * (1 + PROFIT_MARGIN), 2)
    sell_inc = round(sell_ex * (1 + VAT_DEFAULT), 2)
    profit_abs = round(buy_ex * PROFIT_MARGIN, 2)

    payload = {
        "Name": str(name).strip(),
        "Brand": str(brand).strip() if brand else None,
        "BuyPriceEx": buy_ex,
        "BuyPriceInc": buy_inc,
        "SellPriceEx": sell_ex,
        "SellPriceInc": sell_inc,
        "ProfitAbs": profit_abs,
        "Quantity": qty,
    }

    try:
        supabase.table("SaleProducts").insert(payload).execute()
    except Exception as e:
        st.exception(e)
        raise

def add_to_cart(row: pd.Series, qty: float, discount: float):
    qty = float(qty)
    discount = float(discount or 0)

    if qty <= 0:
        return "Quantity must be > 0"
    if qty > float(row["Quantity"]):
        return f"Not enough stock for {row['Name']}"

    # Use constant VAT, not a column
    unit_ex = float(row["SellPriceEx"]) * (1 - discount / 100.0)
    unit_inc = unit_ex * (1 + VAT_DEFAULT)
    line_ex = qty * unit_ex
    line_inc = qty * unit_inc

    payload = {
        "SessionID": SESSION_ID,
        "ProductID": int(row["id"]),
        "Name": row["Name"],
        "Brand": row.get("Brand"),
        "Qty": qty,
        "DiscountPct": discount,
        "VATRate": VAT_DEFAULT,          # keep this if SaleCart has a VATRate column
        "UnitSellEx": unit_ex,
        "UnitSellInc": unit_inc,
        "LineTotalEx": line_ex,
        "LineTotalInc": line_inc,
    }

    try:
        supabase.table("SaleCart").insert(payload).execute()
    except Exception as e:
        st.exception(e)
        return "Failed to add to cart"
    return None

def get_cart() -> pd.DataFrame:
    res = supabase.table("SaleCart").select("*").eq("SessionID", SESSION_ID).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def clear_cart():
    try:
        supabase.table("SaleCart").delete().eq("SessionID", SESSION_ID).execute()
    except Exception as e:
        st.exception(e)

def confirm_sell(password: str):
    if password != st.secrets.get("app_password"):
        return "Incorrect password"

    cart = get_cart()
    if cart.empty:
        return "Cart is empty"

    # Deduct stock atomically-ish (simple loop; consider RPC for production)
    for _, c in cart.iterrows():
        pid = int(c["ProductID"])
        qty = float(c["Qty"])

        try:
            prod_res = supabase.table("SaleProducts").select("Quantity").eq("id", pid).execute()
            prod = prod_res.data[0]
        except Exception as e:
            st.exception(e)
            return f"Failed to load product {pid}"

        stock = float(prod["Quantity"])
        if stock < qty:
            return f"Not enough stock for {c['Name']}"

        new_stock = round(stock - qty, 2)
        try:
            supabase.table("SaleProducts").update({"Quantity": new_stock}).eq("id", pid).execute()
        except Exception as e:
            st.exception(e)
            return f"Failed to update stock for {c['Name']}"

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
        if not str(name).strip():
            st.error("Name required.")
        else:
            try:
                add_product(name, brand, buy_ex, qty)
                st.success("✅ Product added successfully!")
                st.rerun()
            except Exception:
                st.error("❌ Failed to add product. See the error details above.")

st.divider()

# --- Product Table ---
search = st.text_input("🔍 Search products (name or brand)")
show_sensitive = st.toggle("👁 Show profit & buy prices", False)
edit_mode = st.toggle("✏️ Edit mode (full manual editing)", False)

df = load_products(search)
if df.empty:
    st.info("No products yet.")
else:
    # Recompute derived fields in non-edit mode from BuyPriceEx using constants
    if not edit_mode:
        df["BuyPriceInc"] = (df["BuyPriceEx"] * (1 + VAT_DEFAULT)).round(2)
        df["SellPriceEx"] = (df["BuyPriceEx"] * (1 + PROFIT_MARGIN)).round(2)
        df["SellPriceInc"] = (df["SellPriceEx"] * (1 + VAT_DEFAULT)).round(2)
        df["ProfitAbs"] = (df["BuyPriceEx"] * PROFIT_MARGIN).round(2)

    cols = ["Name", "Brand", "SellPriceEx", "SellPriceInc", "Quantity"]
    if show_sensitive:
        cols += ["BuyPriceEx", "BuyPriceInc", "ProfitAbs"]

    # Guard: ensure cols exist
    existing_cols = [c for c in cols if c in df.columns]
    edited = st.data_editor(
        df[existing_cols],
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        disabled=not edit_mode,
    )

    if edit_mode and st.button("💾 Save Edits"):
        pw = st.text_input("🔐 Enter admin password", type="password", key="pw_edit")
        if pw == st.secrets.get("app_password"):
            for _, row in edited.iterrows():
                # Map back to original row to get id
                # (Assumes Name is unique; if not, replace with id in the editor)
                rid = df.loc[df["Name"] == row["Name"]].iloc[0]["id"]
                payload_series = pd.Series({
                    "id": rid,
                    "Name": row.get("Name"),
                    "Brand": row.get("Brand"),
                    "BuyPriceEx": row.get("BuyPriceEx", df.loc[df["id"] == rid, "BuyPriceEx"].iloc[0] if "BuyPriceEx" in df else 0),
                    "BuyPriceInc": row.get("BuyPriceInc", df.loc[df["id"] == rid, "BuyPriceInc"].iloc[0] if "BuyPriceInc" in df else 0),
                    "SellPriceEx": row.get("SellPriceEx", df.loc[df["id"] == rid, "SellPriceEx"].iloc[0] if "SellPriceEx" in df else 0),
                    "SellPriceInc": row.get("SellPriceInc", df.loc[df["id"] == rid, "SellPriceInc"].iloc[0] if "SellPriceInc" in df else 0),
                    "ProfitAbs": row.get("ProfitAbs", df.loc[df["id"] == rid, "ProfitAbs"].iloc[0] if "ProfitAbs" in df else 0),
                    "Quantity": row.get("Quantity", df.loc[df["id"] == rid, "Quantity"].iloc[0] if "Quantity" in df else 0),
                })
                save_product_row(payload_series)

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
    # Recompute totals for display (in case DB didn’t calculate)
    cart["LineTotalEx"] = cart["Qty"] * cart["UnitSellEx"]
    cart["LineTotalInc"] = cart["Qty"] * cart["UnitSellInc"]
    st.dataframe(cart[["Name", "Brand", "Qty", "DiscountPct", "LineTotalEx", "LineTotalInc"]], use_container_width=True)

    total_ex = float(cart["LineTotalEx"].sum())
    total_inc = float(cart["LineTotalInc"].sum())
    st.markdown(f"**Total excl. VAT: €{total_ex:.2f}** | **Total incl. VAT: €{total_inc:.2f}**")

    pw = st.text_input("🔐 Password to confirm sale", type="password", key="pw_cart")
    if st.button("✅ Confirm Sale"):
        msg = confirm_sell(pw)
        if msg:
            st.error(msg)
        else:
            st.success("✅ Sale confirmed, inventory updated.")
            st.rerun()
