import streamlit as st
import pandas as pd
import uuid
from supabase import create_client, Client

st.set_page_config(page_title="🛍️ Retail Sales", layout="wide")

VAT_DEFAULT = 0.255  # 25.5% as in the rest of your app

# ---------- Supabase ----------
@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_client()

# ---------- Session ID for cart ----------
if "retail_session_id" not in st.session_state:
    st.session_state["retail_session_id"] = str(uuid.uuid4())
SESSION_ID = st.session_state["retail_session_id"]

# ---------- Helpers ----------
def load_sale_products(search: str = "") -> pd.DataFrame:
    q = supabase.table("SaleProducts").select("*")
    if search:
        # OR filter (ilike) across Name / Brand
        q = supabase.table("SaleProducts").select("*").or_(
            f'Name.ilike.%{search}%,Brand.ilike.%{search}%'
        )
    res = q.execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=[
        "id","Name","Brand","BuyPriceEx","VATRate","SellPriceEx","Quantity"
    ])

def save_product_row(row: pd.Series):
    # Update editable columns only
    supabase.table("SaleProducts").update({
        "Name": row["Name"],
        "Brand": row["Brand"],
        "BuyPriceEx": float(row["BuyPriceEx"]),
        "VATRate": float(row["VATRate"]),
        "SellPriceEx": float(row["SellPriceEx"]),
        "Quantity": float(row["Quantity"])
    }).eq("id", row["id"]).execute()

def add_to_cart(product_row: pd.Series, qty: float, discount_pct: float):
    if qty <= 0:
        return "Quantity must be > 0."
    if float(product_row["Quantity"]) < qty:
        return "Not enough stock."
    vat = float(product_row.get("VATRate", VAT_DEFAULT) or VAT_DEFAULT)
    sell_ex = float(product_row.get("SellPriceEx", 0) or 0)
    # discount applies to SellPriceEx
    unit_ex = round(sell_ex * (1 - discount_pct / 100.0), 2)
    unit_inc = round(unit_ex * (1 + vat), 2)
    line_ex = round(unit_ex * qty, 2)
    line_inc = round(unit_inc * qty, 2)

    supabase.table("SaleCart").insert({
        "SessionID": SESSION_ID,
        "ProductID": int(product_row["id"]),
        "Name": product_row["Name"],
        "Brand": product_row.get("Brand"),
        "Qty": float(qty),
        "DiscountPct": float(discount_pct),
        "VATRate": vat,
        "UnitSellEx": unit_ex,
        "UnitSellInc": unit_inc,
        "LineTotalEx": line_ex,
        "LineTotalInc": line_inc
    }).execute()
    return None

def get_cart() -> pd.DataFrame:
    res = supabase.table("SaleCart").select("*").eq("SessionID", SESSION_ID).order("CreatedAt").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=[
        "id","ProductID","Name","Brand","Qty","DiscountPct","VATRate","UnitSellEx","UnitSellInc","LineTotalEx","LineTotalInc"
    ])

def clear_cart():
    supabase.table("SaleCart").delete().eq("SessionID", SESSION_ID).execute()

def confirm_sell(password: str) -> str | None:
    if password != st.secrets.get("app_password"):
        return "Incorrect password."

    cart = get_cart()
    if cart.empty:
        return "Cart is empty."

    # Check stock first
    # Fetch all product rows we need in one go
    product_ids = cart["ProductID"].unique().tolist()
    products = supabase.table("SaleProducts").select("*").in_("id", product_ids).execute().data
    by_id = {p["id"]: p for p in products}

    # Validate availability
    for _, line in cart.iterrows():
        pid = int(line["ProductID"])
        qty_needed = float(line["Qty"])
        stock = float(by_id[pid]["Quantity"])
        if stock < qty_needed:
            return f"Insufficient stock for {by_id[pid]['Name']} (have {stock}, need {qty_needed})."

    # Deduct stock
    for _, line in cart.iterrows():
        pid = int(line["ProductID"])
        qty_needed = float(line["Qty"])
        stock = float(by_id[pid]["Quantity"])
        new_stock = round(stock - qty_needed, 2)
        supabase.table("SaleProducts").update({"Quantity": new_stock}).eq("id", pid).execute()

    # Clear cart
    clear_cart()
    return None

# ---------- UI ----------
st.title("🛍️ Retail Sales")

with st.expander("Products for Sale (Inventory)"):
    left, right = st.columns([2,1])
    with left:
        search = st.text_input("🔍 Search (name / brand)")
    with right:
        show_sensitive = st.toggle("👁 Show buy prices & profit", value=False)

    df = load_sale_products(search)

    if df.empty:
        st.info("No items yet. Add via your Excel import script.")
    else:
        # computed columns for display only
        df["_BuyPriceInc"]  = (df["BuyPriceEx"].astype(float) * (1 + df["VATRate"].astype(float))).round(2)
        df["_SellPriceInc"] = (df["SellPriceEx"].astype(float) * (1 + df["VATRate"].astype(float))).round(2)
        df["_ProfitAbsEx"]  = (df["SellPriceEx"].astype(float) - df["BuyPriceEx"].astype(float)).round(2)

        # Build a view dataframe
        base_cols = ["id","Name","Brand","SellPriceEx","_SellPriceInc","Quantity","VATRate"]
        sensitive_cols = ["BuyPriceEx","_BuyPriceInc","_ProfitAbsEx"]
        cols = base_cols + (sensitive_cols if show_sensitive else [])
        view = df[cols].rename(columns={
            "SellPriceEx": "SellPrice (excl. VAT)",
            "_SellPriceInc": "SellPrice (incl. VAT)",
            "BuyPriceEx": "BuyPrice (excl. VAT)",
            "_BuyPriceInc": "BuyPrice (incl. VAT)",
            "_ProfitAbsEx": "Profit (abs, excl. VAT)",
            "VATRate": "VAT"
        })

        st.markdown("**Tip:** Edit prices/stock directly in the grid. Use the 🔽 per-row cart controls to sell.")
        edited = st.data_editor(
            view,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "VAT": st.column_config.NumberColumn(format="%.3f"),
                "SellPrice (excl. VAT)": st.column_config.NumberColumn(format="%.2f"),
                "SellPrice (incl. VAT)": st.column_config.NumberColumn(format="%.2f", disabled=True),
                "BuyPrice (excl. VAT)": st.column_config.NumberColumn(format="%.2f", disabled=not show_sensitive),
                "BuyPrice (incl. VAT)": st.column_config.NumberColumn(format="%.2f", disabled=True),
                "Profit (abs, excl. VAT)": st.column_config.NumberColumn(format="%.2f", disabled=True),
                "Quantity": st.column_config.NumberColumn(format="%.2f"),
            },
            key="sale_products_editor"
        )

        # Save updates (asks for password)
        if st.button("💾 Save Product Changes"):
            pw = st.text_input("🔐 Enter admin password to save product changes", type="password", key="pw_save_products")
            if pw == st.secrets.get("app_password"):
                # Map back edited -> main df columns
                # (recompute SellPriceEx, BuyPriceEx, VAT, Quantity from edited)
                # We rely on 'id' to find the real row in df
                edited_merged = edited.merge(df[["id","BuyPriceEx","SellPriceEx","Quantity","VATRate","Name","Brand"]], on="id", how="left", suffixes=("_edited",""))
                for _, row in edited.iterrows():
                    rid = int(row["id"])
                    # Get raw source row
                    src = df.loc[df["id"] == rid].iloc[0]
                    # Pull edited fields safely
                    vat = float(row.get("VAT", src["VATRate"]))
                    qty = float(row.get("Quantity", src["Quantity"]))
                    sell_ex = float(row.get("SellPrice (excl. VAT)", src["SellPriceEx"]))
                    buy_ex = float(row.get("BuyPrice (excl. VAT)", src["BuyPriceEx"])) if show_sensitive else float(src["BuyPriceEx"])
                    name = row.get("Name", src["Name"])
                    brand = row.get("Brand", src["Brand"])
                    save_product_row(pd.Series({
                        "id": rid,
                        "Name": name,
                        "Brand": brand,
                        "BuyPriceEx": buy_ex,
                        "VATRate": vat,
                        "SellPriceEx": sell_ex,
                        "Quantity": qty
                    }))
                st.success("✅ Product changes saved.")
                st.rerun()
            else:
                st.error("❌ Incorrect password — no changes saved.")

        st.markdown("---")

        # Per-row cart controls
        st.subheader("🧺 Add to Cart")
        for _, row in df.iterrows():
            with st.expander(f'{row["Name"]} — stock: {row["Quantity"]}'):
                c1, c2, c3 = st.columns([1,1,2])
                with c1:
                    qty = st.number_input("Qty", min_value=0.0, step=1.0, key=f"qty_{row['id']}")
                with c2:
                    disc = st.number_input("Discount %", min_value=0.0, max_value=100.0, step=1.0, key=f"disc_{row['id']}")
                with c3:
                    if st.button("➕ Add to Cart", key=f"add_{row['id']}"):
                        err = add_to_cart(row, qty, disc)
                        if err:
                            st.error(err)
                        else:
                            st.success("Added to cart.")
                            st.rerun()

# CART
st.divider()
st.subheader("🧾 Current Cart")

cart = get_cart()
if cart.empty:
    st.info("Cart is empty.")
else:
    # Recalculate line totals (display only)
    cart_disp = cart.copy()
    cart_disp["LineTotalEx"] = (cart_disp["Qty"].astype(float) * cart_disp["UnitSellEx"].astype(float)).round(2)
    cart_disp["LineTotalInc"] = (cart_disp["Qty"].astype(float) * cart_disp["UnitSellInc"].astype(float)).round(2)

    st.dataframe(
        cart_disp[["Name","Brand","Qty","DiscountPct","UnitSellEx","UnitSellInc","LineTotalEx","LineTotalInc"]],
        use_container_width=True
    )

    total_ex = float(cart_disp["LineTotalEx"].sum())
    total_inc = float(cart_disp["LineTotalInc"].sum())
    st.markdown(f"### Total (excl. VAT): **€{total_ex:.2f}**  |  Total (incl. VAT): **€{total_inc:.2f}**")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑️ Clear Cart"):
            clear_cart()
            st.success("Cart cleared.")
            st.rerun()
    with c2:
        if st.button("✅ Confirm Sell"):
            pw = st.text_input("🔐 Enter admin password to confirm sale", type="password", key="pw_confirm")
            msg = confirm_sell(pw)
            if msg is None:
                st.success("✅ Sale confirmed. Stock updated and cart cleared.")
                st.rerun()
            else:
                st.error(f"❌ {msg}")
