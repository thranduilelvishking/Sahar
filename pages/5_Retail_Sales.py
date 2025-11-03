import streamlit as st
import pandas as pd
import uuid
import time
from supabase import create_client, Client

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="🛍️ Retail Sales", layout="wide")

# ---------- CONSTANTS ----------
VAT_DEFAULT = 0.255   # 25.5% VAT
PROFIT_MARGIN = 0.5   # 50% margin on BuyPriceEx

# ---------- SUPABASE ----------
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

# ---------- HELPERS ----------
def safe_execute(func, retries=1, delay=0.5):
    for i in range(retries + 1):
        try:
            return func()
        except Exception as e:
            if i == retries:
                st.exception(e)
                raise
            time.sleep(delay)

# ---------- DB: PRODUCTS ----------
def load_products(search: str = "") -> pd.DataFrame:
    q = supabase.table("SaleProducts").select("*")
    if search:
        q = q.or_(f"Name.ilike.%{search}%,Brand.ilike.%{search}%")
    res = safe_execute(lambda: q.execute())
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def add_product(name: str, brand: str, buy_ex: float, qty: float) -> None:
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

def save_product_row(row: pd.Series) -> None:
    data = {
        "Name": row["Name"],
        "Brand": row.get("Brand") or None,
        "BuyPriceEx": float(row.get("BuyPriceEx", 0)),
        "BuyPriceInc": float(row.get("BuyPriceInc", 0)),
        "SellPriceEx": float(row.get("SellPriceEx", 0)),
        "SellPriceInc": float(row.get("SellPriceInc", 0)),
        "ProfitAbs": float(row.get("ProfitAbs", 0)),
        "Quantity": float(row.get("Quantity", 0)),
        "UpdatedAt": "now()",
    }
    safe_execute(lambda: supabase.table("SaleProducts").update(data).eq("id", row["id"]).execute())

# ---------- DB: CART ----------
def add_to_cart(product_row: pd.Series, qty: float) -> str | None:
    qty = float(qty)
    if qty <= 0:
        return "Quantity must be > 0"
    if qty > float(product_row["Quantity"]):
        return f"Not enough stock for {product_row['Name']}"

    # Initial unit prices without discount (discount edited later in cart)
    unit_ex = float(product_row["SellPriceEx"])
    unit_inc = float(product_row["SellPriceInc"])

    existing = safe_execute(
        lambda: supabase.table("SaleCart")
        .select("id,Qty,DiscountPct,UnitSellEx,UnitSellInc")
        .eq("SessionID", SESSION_ID)
        .eq("ProductID", product_row["id"])
        .execute()
    )

    if existing.data:
        # Keep whatever discount the row already had
        cid = existing.data[0]["id"]
        current_qty = float(existing.data[0]["Qty"])
        current_disc = float(existing.data[0].get("DiscountPct", 0) or 0)

        # Apply existing discount to current units
        disc_factor = (1 - current_disc / 100.0)
        u_ex = round(unit_ex * disc_factor, 2)
        u_inc = round(u_ex * (1 + VAT_DEFAULT), 2)

        new_qty = current_qty + qty
        safe_execute(
            lambda: supabase.table("SaleCart")
            .update({
                "Qty": new_qty,
                "VATRate": VAT_DEFAULT,
                "UnitSellEx": u_ex,
                "UnitSellInc": u_inc,
                "LineTotalEx": u_ex * new_qty,
                "LineTotalInc": u_inc * new_qty,
            })
            .eq("id", cid)
            .execute()
        )
    else:
        # No discount initially
        safe_execute(
            lambda: supabase.table("SaleCart").insert({
                "SessionID": SESSION_ID,
                "ProductID": product_row["id"],
                "Name": product_row["Name"],
                "Brand": product_row.get("Brand"),
                "Qty": qty,
                "DiscountPct": 0.0,
                "VATRate": VAT_DEFAULT,         # NOT NULL in your schema
                "UnitSellEx": unit_ex,
                "UnitSellInc": unit_inc,
                "LineTotalEx": unit_ex * qty,
                "LineTotalInc": unit_inc * qty,
            }).execute()
        )
    return None

def get_cart() -> pd.DataFrame:
    res = safe_execute(lambda: supabase.table("SaleCart").select("*").eq("SessionID", SESSION_ID).execute())
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def update_cart_quantity(cart_id: int, new_qty: float) -> None:
    # Pull row for prices + product_id for stock check
    item = safe_execute(lambda: supabase.table("SaleCart")
                        .select("ProductID,DiscountPct")
                        .eq("id", cart_id).execute())
    if not item.data:
        return
    product_id = int(item.data[0]["ProductID"])
    discount = float(item.data[0].get("DiscountPct", 0) or 0)

    prod = safe_execute(lambda: supabase.table("SaleProducts")
                        .select("SellPriceEx,SellPriceInc,Quantity")
                        .eq("id", product_id).execute()).data[0]
    stock = float(prod["Quantity"])
    base_ex = float(prod["SellPriceEx"])

    new_qty = max(0.0, float(new_qty))
    if new_qty > stock:
        st.warning("⚠️ Cannot exceed available stock.")
        new_qty = stock

    # Apply discount to base price
    disc_factor = (1 - discount / 100.0)
    u_ex = round(base_ex * disc_factor, 2)
    u_inc = round(u_ex * (1 + VAT_DEFAULT), 2)

    safe_execute(lambda: supabase.table("SaleCart").update({
        "Qty": new_qty,
        "VATRate": VAT_DEFAULT,
        "UnitSellEx": u_ex,
        "UnitSellInc": u_inc,
        "LineTotalEx": u_ex * new_qty,
        "LineTotalInc": u_inc * new_qty,
    }).eq("id", cart_id).execute())

def update_cart_discount(cart_id: int, new_discount: float) -> None:
    # Clamp discount and recompute unit + line totals using current qty
    row = safe_execute(lambda: supabase.table("SaleCart")
                       .select("ProductID,Qty")
                       .eq("id", cart_id).execute()).data[0]
    product_id = int(row["ProductID"])
    qty = float(row["Qty"])

    prod = safe_execute(lambda: supabase.table("SaleProducts")
                        .select("SellPriceEx")
                        .eq("id", product_id).execute()).data[0]
    base_ex = float(prod["SellPriceEx"])

    new_discount = min(max(float(new_discount), 0.0), 100.0)
    disc_factor = (1 - new_discount / 100.0)
    u_ex = round(base_ex * disc_factor, 2)
    u_inc = round(u_ex * (1 + VAT_DEFAULT), 2)

    safe_execute(lambda: supabase.table("SaleCart").update({
        "DiscountPct": new_discount,
        "VATRate": VAT_DEFAULT,
        "UnitSellEx": u_ex,
        "UnitSellInc": u_inc,
        "LineTotalEx": u_ex * qty,
        "LineTotalInc": u_inc * qty,
    }).eq("id", cart_id).execute())

def clear_cart() -> None:
    safe_execute(lambda: supabase.table("SaleCart").delete().eq("SessionID", SESSION_ID).execute())

def confirm_sell(password: str) -> str | None:
    if password != st.secrets.get("app_password"):
        return "Incorrect password"
    cart = get_cart()
    if cart.empty:
        return "Cart is empty"

    # Deduct stock
    for _, c in cart.iterrows():
        pid = int(c["ProductID"])
        qty = float(c["Qty"])
        prod = safe_execute(lambda: supabase.table("SaleProducts")
                            .select("Quantity")
                            .eq("id", pid).execute()).data[0]
        stock = float(prod["Quantity"])
        if stock < qty:
            return f"Not enough stock for {c['Name']}"
        new_stock = round(stock - qty, 2)
        safe_execute(lambda: supabase.table("SaleProducts").update({
            "Quantity": new_stock,
            "UpdatedAt": "now()",
        }).eq("id", pid).execute())

    clear_cart()
    return None

# ---------- UI ----------
st.title("🛍️ Retail Sales Manager")

# Add to Inventory
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

# Product Table (with show/hide & manual edit)
search = st.text_input("🔍 Search products (name or brand)")
show_sensitive = st.toggle("👁 Show profit & buy prices", False)
edit_mode = st.toggle("✏️ Edit mode (manual)", False)

df = load_products(search)
if df.empty:
    st.info("No products yet.")
else:
    # Derived values (not stored) for display and non-edit mode
    df["BuyPriceInc"] = (df["BuyPriceEx"] * (1 + VAT_DEFAULT)).round(2)
    df["SellPriceEx"] = (df["BuyPriceEx"] * (1 + PROFIT_MARGIN)).round(2)
    df["SellPriceInc"] = (df["SellPriceEx"] * (1 + VAT_DEFAULT)).round(2)
    df["ProfitAbs"]  = (df["BuyPriceEx"] * PROFIT_MARGIN).round(2)

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
            # columns: Name | Price ex | Price inc | Stock | Qty | Add
            c1, c2, c3, c4, c5, c6 = st.columns([4, 2, 2, 2, 2, 1])

            # avoid duplicate look if brand==name
            brand_text = f"\n{row['Brand']}" if row.get("Brand") and row["Brand"] != row["Name"] else ""
            c1.markdown(f"**{row['Name']}**{brand_text}")

            c2.markdown(f"€{row['SellPriceEx']:.2f} excl. VAT")
            c3.markdown(f"€{row['SellPriceInc']:.2f} incl. VAT")
            c4.markdown(f"Stock: {row['Quantity']}")

            qty_input = c5.number_input(
                f"Qty_{idx}",
                min_value=1.0,
                max_value=float(max(row["Quantity"], 1.0)),
                step=1.0,
                value=1.0,
                label_visibility="collapsed",
                key=f"qty_inp_{idx}"
            )

            if c6.button("🛒", key=f"addcart_{idx}"):
                msg = add_to_cart(row, qty_input)
                if msg:
                    st.error(msg)
                else:
                    st.success(f"Added {qty_input:.0f} × {row['Name']}")
                    st.rerun()

            if show_sensitive:
                c1.caption(
                    f"Buy ex: €{row['BuyPriceEx']:.2f} | "
                    f"Buy inc: €{row['BuyPriceInc']:.2f} | "
                    f"Profit: €{row['ProfitAbs']:.2f}"
                )

st.divider()

# Cart Section (with Discount column)
st.subheader("🧾 Shopping Cart")
cart = get_cart()
if cart.empty:
    st.info("Cart empty.")
else:
    # Per-row controls: qty +/- and discount editor
    for idx, c in cart.iterrows():
        c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([4, 2, 2, 2, 2, 1, 1, 2, 1])
        c1.markdown(f"**{c['Name']}**" + (f"\n{c['Brand']}" if c.get("Brand") and c["Brand"] != c["Name"] else ""))

        c2.markdown(f"€{c['UnitSellEx']:.2f} ex")
        c3.markdown(f"€{c['UnitSellInc']:.2f} inc")
        c4.markdown(f"€{c['LineTotalEx']:.2f} ex")
        c5.markdown(f"€{c['LineTotalInc']:.2f} inc")

        dec = c6.button("➖", key=f"dec_{idx}")
        inc = c7.button("➕", key=f"inc_{idx}")
        if dec and c["Qty"] > 0:
            update_cart_quantity(c["id"], c["Qty"] - 1)
            st.rerun()
        if inc:
            update_cart_quantity(c["id"], c["Qty"] + 1)
            st.rerun()

        # Discount column (in CART, not in inventory)
        new_disc = c8.number_input(
            f"Disc%_{idx}",
            min_value=0.0, max_value=100.0, step=1.0,
            value=float(c.get("DiscountPct", 0) or 0),
            format="%.0f", label_visibility="visible"
        )
        if c9.button("Update", key=f"discbtn_{idx}"):
            update_cart_discount(c["id"], new_disc)
            st.success("Discount updated")
            st.rerun()

        c1.caption(f"Qty: {c['Qty']:.0f}  |  Disc: {float(c.get('DiscountPct',0) or 0):.0f}%")

    # Refresh cart after edits
    cart = get_cart()
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
