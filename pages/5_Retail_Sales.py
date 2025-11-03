import streamlit as st
import pandas as pd
import uuid
import time
from supabase import create_client, Client

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="🛍️ Retail Sales", layout="wide")

# ---------- CONSTANTS ----------
VAT_DEFAULT = 0.255   # 25.5% VAT
PROFIT_MARGIN = 0.5   # 50% profit margin

# ---------- SUPABASE CONNECTION ----------
@st.cache_resource(ttl=3600)
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_client()

# ---------- SESSION ----------
if "retail_session_id" not in st.session_state:
    st.session_state["retail_session_id"] = str(uuid.uuid4())
SESSION_ID = st.session_state["retail_session_id"]

# ---------- SAFE EXECUTE ----------
def safe_execute(func, retries=1, delay=0.5):
    for i in range(retries + 1):
        try:
            return func()
        except Exception as e:
            if i == retries:
                st.exception(e)
                raise
            time.sleep(delay)

# ---------- DATABASE HELPERS ----------
def load_products(search=""):
    q = supabase.table("SaleProducts").select("*")
    if search:
        q = q.or_(f"Name.ilike.%{search}%,Brand.ilike.%{search}%")
    res = safe_execute(lambda: q.execute())
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def save_product_row(row):
    data = {
        "Name": row["Name"],
        "Brand": row.get("Brand", ""),
        "BuyPriceEx": float(row.get("BuyPriceEx", 0)),
        "BuyPriceInc": float(row.get("BuyPriceInc", 0)),
        "SellPriceEx": float(row.get("SellPriceEx", 0)),
        "SellPriceInc": float(row.get("SellPriceInc", 0)),
        "ProfitAbs": float(row.get("ProfitAbs", 0)),
        "Quantity": float(row.get("Quantity", 0)),
        "UpdatedAt": "now()",
    }
    safe_execute(lambda: supabase.table("SaleProducts").update(data).eq("id", row["id"]).execute())

def add_product(name, brand, buy_ex, qty):
    buy_ex = float(buy_ex)
    qty = float(qty)

    buy_inc = round(buy_ex * (1 + VAT_DEFAULT), 2)
    sell_ex = round(buy_ex * (1 + PROFIT_MARGIN), 2)
    sell_inc = round(sell_ex * (1 + VAT_DEFAULT), 2)
    profit_abs = round(buy_ex * PROFIT_MARGIN, 2)

    data = {
        "Name": name.strip(),
        "Brand": brand.strip() if brand else None,
        "BuyPriceEx": buy_ex,
        "BuyPriceInc": buy_inc,
        "SellPriceEx": sell_ex,
        "SellPriceInc": sell_inc,
        "ProfitAbs": profit_abs,
        "Quantity": qty,
        "UpdatedAt": "now()",
    }
    safe_execute(lambda: supabase.table("SaleProducts").insert(data).execute())

def add_to_cart(row, qty, discount):
    qty = float(qty)
    discount = float(discount)
    if qty <= 0:
        return "Quantity must be > 0"
    if qty > float(row["Quantity"]):
        return f"Not enough stock for {row['Name']}"

    # discounted price
    unit_ex = round(row["SellPriceEx"] * (1 - discount / 100), 2)
    unit_inc = round(unit_ex * (1 + VAT_DEFAULT), 2)

    existing = safe_execute(
        lambda: supabase.table("SaleCart")
        .select("id,Qty")
        .eq("SessionID", SESSION_ID)
        .eq("ProductID", row["id"])
        .execute()
    )

    if existing.data:
        cid = existing.data[0]["id"]
        new_qty = float(existing.data[0]["Qty"]) + qty
        safe_execute(
            lambda: supabase.table("SaleCart")
            .update({
                "Qty": new_qty,
                "DiscountPct": discount,
                "VATRate": VAT_DEFAULT,
                "UnitSellEx": unit_ex,
                "UnitSellInc": unit_inc,
                "LineTotalEx": unit_ex * new_qty,
                "LineTotalInc": unit_inc * new_qty,
            })
            .eq("id", cid)
            .execute()
        )
    else:
        safe_execute(
            lambda: supabase.table("SaleCart").insert({
                "SessionID": SESSION_ID,
                "ProductID": row["id"],
                "Name": row["Name"],
                "Brand": row["Brand"],
                "Qty": qty,
                "DiscountPct": discount,
                "VATRate": VAT_DEFAULT,
                "UnitSellEx": unit_ex,
                "UnitSellInc": unit_inc,
                "LineTotalEx": unit_ex * qty,
                "LineTotalInc": unit_inc * qty,
            }).execute()
        )
    return None

def get_cart():
    res = safe_execute(lambda: supabase.table("SaleCart").select("*").eq("SessionID", SESSION_ID).execute())
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def update_cart_quantity(cid, new_qty):
    try:
        item = safe_execute(lambda: supabase.table("SaleCart")
                            .select("ProductID,UnitSellEx,UnitSellInc,Qty")
                            .eq("id", cid).execute())
        if not item.data:
            return
        product_id = int(item.data[0]["ProductID"])
        unit_ex = float(item.data[0]["UnitSellEx"])
        unit_inc = float(item.data[0]["UnitSellInc"])
        prod = safe_execute(lambda: supabase.table("SaleProducts")
                            .select("Quantity").eq("id", product_id).execute()).data[0]
        stock = float(prod["Quantity"])
        new_qty = float(new_qty)
        if new_qty < 0:
            new_qty = 0
        if new_qty > stock:
            st.warning("⚠️ Cannot exceed available stock.")
            new_qty = stock
        safe_execute(
            lambda: supabase.table("SaleCart")
            .update({
                "Qty": new_qty,
                "LineTotalEx": unit_ex * new_qty,
                "LineTotalInc": unit_inc * new_qty,
            })
            .eq("id", cid)
            .execute()
        )
    except Exception as e:
        st.error(f"Error updating quantity: {e}")

def clear_cart():
    safe_execute(lambda: supabase.table("SaleCart").delete().eq("SessionID", SESSION_ID).execute())

def confirm_sell(password):
    if password != st.secrets.get("app_password"):
        return "Incorrect password"
    cart = get_cart()
    if cart.empty:
        return "Cart is empty"

    for _, c in cart.iterrows():
        pid = int(c["ProductID"])
        qty = float(c["Qty"])
        prod = safe_execute(lambda: supabase.table("SaleProducts").select("Quantity").eq("id", pid).execute()).data[0]
        stock = float(prod["Quantity"])
        if stock < qty:
            return f"Not enough stock for {c['Name']}"
        new_stock = round(stock - qty, 2)
        safe_execute(lambda: supabase.table("SaleProducts").update({
            "Quantity": new_stock,
            "UpdatedAt": "now()"
        }).eq("id", pid).execute())

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
    if st.form_submit_button("Add Product"):
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
edit_mode = st.toggle("✏️ Edit mode (manual)", False)

df = load_products(search)
if df.empty:
    st.info("No products yet.")
else:
    df["BuyPriceInc"] = (df["BuyPriceEx"] * (1 + VAT_DEFAULT)).round(2)
    df["SellPriceEx"] = (df["BuyPriceEx"] * (1 + PROFIT_MARGIN)).round(2)
    df["SellPriceInc"] = (df["SellPriceEx"] * (1 + VAT_DEFAULT)).round(2)
    df["ProfitAbs"] = (df["BuyPriceEx"] * PROFIT_MARGIN).round(2)

    cols = ["Name", "Brand", "SellPriceEx", "SellPriceInc", "Quantity"]
    if show_sensitive:
        cols += ["BuyPriceEx", "BuyPriceInc", "ProfitAbs"]

    if edit_mode:
        edited = st.data_editor(df[cols], use_container_width=True, hide_index=True)
        if st.button("💾 Save Edits"):
            for _, row in edited.iterrows():
                rid = df.loc[df["Name"] == row["Name"], "id"].iloc[0]
                save_product_row(pd.Series({"id": rid, **row.to_dict()}))
            st.success("✅ Saved changes.")
            st.rerun()
    else:
        st.subheader("📦 Inventory")
        for idx, row in df.iterrows():
            c1, c2, c3, c4, c5, c6, c7 = st.columns([4, 2, 2, 2, 2, 2, 1])
            c1.markdown(f"**{row['Name']}**  \n{row.get('Brand') or ''}")
            c2.markdown(f"€{row['SellPriceEx']:.2f} excl. VAT")
            c3.markdown(f"€{row['SellPriceInc']:.2f} incl. VAT")
            c4.markdown(f"Stock: {row['Quantity']}")
            qty_input = c5.number_input(
                f"Qty_{idx}", min_value=1.0,
                max_value=float(max(row["Quantity"], 1.0)),
                step=1.0, value=1.0, label_visibility="collapsed",
            )
            discount_input = c6.number_input(
                f"Disc_{idx}", min_value=0.0, max_value=100.0,
                step=1.0, value=0.0, label_visibility="collapsed",
            )
            if c7.button("🛒", key=f"addcart_{idx}"):
                msg = add_to_cart(row, qty_input, discount_input)
                if msg:
                    st.error(msg)
                else:
                    st.success(f"Added {qty_input:.0f} × {row['Name']} ({discount_input:.0f}% off)")
                    st.rerun()

            if show_sensitive:
                c1.caption(
                    f"Buy ex: €{row['BuyPriceEx']:.2f} | "
                    f"Buy inc: €{row['BuyPriceInc']:.2f} | "
                    f"Profit: €{row['ProfitAbs']:.2f}"
                )

st.divider()

# --- Cart Section ---
st.subheader("🧾 Shopping Cart")
cart = get_cart()
if cart.empty:
    st.info("Cart empty.")
else:
    for idx, c in cart.iterrows():
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([4, 2, 2, 2, 2, 1, 1, 2])
        c1.markdown(f"**{c['Name']}**  \n{c.get('Brand') or ''}")
        c2.markdown(f"€{c['UnitSellEx']:.2f} ex")
        c3.markdown(f"€{c['UnitSellInc']:.2f} inc")
        c4.markdown(f"€{c['LineTotalEx']:.2f} ex")
        c5.markdown(f"€{c['LineTotalInc']:.2f} inc")
        dec = c6.button("➖", key=f"dec_{idx}")
        inc = c7.button("➕", key=f"inc_{idx}")
        c8.caption(f"Qty: {c['Qty']:.0f}  |  Disc: {c['DiscountPct']:.0f}%")
        if dec and c["Qty"] > 0:
            update_cart_quantity(c["id"], c["Qty"] - 1)
            st.rerun()
        if inc:
            update_cart_quantity(c["id"], c["Qty"] + 1)
            st.rerun()

    cart = get_cart()  # refresh
    if not cart.empty:
        total_ex = float(cart["LineTotalEx"].sum())
        total_inc = float(cart["LineTotalInc"].sum())
        vat_total = round(total_inc - total_ex, 2)
        total_items = int(cart["Qty"].sum())

        st.markdown("---")
        st.markdown("### 🧮 Totals")
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Items", total_items)
        t2.metric("Subtotal (excl. VAT)", f"€{total_ex:.2f}")
        t3.metric("VAT (25.5%)", f"€{vat_total:.2f}")
        t4.metric("Total (incl. VAT)", f"€{total_inc:.2f}")

        st.markdown("---")
        pw = st.text_input("🔐 Password to confirm sale", type="password", key="pw_cart")
        col_ok, col_clear = st.columns([1,1])
        if col_ok.button("✅ Confirm Sale"):
            msg = confirm_sell(pw)
            if msg:
                st.error(msg)
            else:
                st.success("✅ Sale confirmed and inventory updated.")
                st.rerun()
        if col_clear.button("🗑️ Clear Cart"):
            clear_cart()
            st.success("Cart cleared.")
            st.rerun()
