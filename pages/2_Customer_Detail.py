import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client, Client

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Customer Detail", layout="wide")

# ---------- CONNECT TO SUPABASE ----------
@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_connection()

# ---------- DATA HELPERS ----------
def get_customer(customer_no):
    res = supabase.table("Customers").select("*").eq("CustomerNo", customer_no).execute()
    return res.data[0] if res.data else None

def get_visits(customer_no):
    res = supabase.table("Visits").select("*").eq("CustomerNo", customer_no).order("Date", desc=True).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def get_products_used(visit_pk):
    res = supabase.table("ProductsUsed").select("*").eq("VisitPK", visit_pk).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def get_products_list():
    res = supabase.table("Products").select("ProductName, Brand, ColorNo, PricePerGram").order("Brand").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def add_visit(customer_no, visit_date, service, total_price):
    """Add visit; assign per-customer VisitID and compute VAT & net income."""
    vat = round(total_price * 0.255, 2)
    net_income = round(total_price - vat - 2, 2)

    existing = supabase.table("Visits").select("VisitID").eq("CustomerNo", customer_no).order("VisitID", desc=True).limit(1).execute()
    next_visit_id = 1
    if existing.data:
        last = existing.data[0].get("VisitID")
        if last:
            next_visit_id = last + 1

    response = supabase.table("Visits").insert({
        "CustomerNo": customer_no,
        "VisitID": next_visit_id,
        "Date": str(visit_date),
        "Service": service,
        "TotalPrice_Gross": total_price,
        "VAT": vat,
        "NetIncome": net_income
    }).execute()

    if response.data and len(response.data) > 0:
        return response.data[0].get("VisitPK")
    return None

def add_product_used(visit_pk, product_name, weight_used):
    """Add product usage and update visit NetIncome accordingly."""
    pinfo = supabase.table("Products").select("Brand, ColorNo, PricePerGram").eq("ProductName", product_name).execute()
    if pinfo.data:
        brand = pinfo.data[0]["Brand"]
        color = pinfo.data[0]["ColorNo"]
        price_per_g = float(pinfo.data[0]["PricePerGram"])
        cost = round(weight_used * price_per_g, 2)
    else:
        brand, color, cost = None, None, 0.0

    supabase.table("ProductsUsed").insert({
        "VisitPK": visit_pk,
        "Product": product_name,
        "Brand": brand,
        "ColorNo": color,
        "WeightUsed_g": weight_used,
        "ProductCost": cost
    }).execute()

    # update NetIncome
    used = supabase.table("ProductsUsed").select("ProductCost").eq("VisitPK", visit_pk).execute()
    total_cost = sum(float(p["ProductCost"]) for p in used.data) if used.data else 0
    visit = supabase.table("Visits").select("TotalPrice_Gross, VAT").eq("VisitPK", visit_pk).execute()
    if visit.data:
        gross = float(visit.data[0]["TotalPrice_Gross"])
        vat = float(visit.data[0]["VAT"])
        new_net = round(gross - vat - total_cost - 2, 2)
        supabase.table("Visits").update({"NetIncome": new_net}).eq("VisitPK", visit_pk).execute()

# ---------- PAGE BODY ----------
st.title("🌸 Customer Detail")

# get parameter from URL
customer_no = st.query_params.get("customer_no", [None])[0]

if not customer_no:
    st.warning("No customer selected. Please go back to the Customers page.")
    st.stop()

customer = get_customer(customer_no)
if not customer:
    st.error(f"No customer found with number {customer_no}.")
    st.stop()

st.header(f"{customer['FullName']} (#{customer['CustomerNo']})")
st.write(f"📞 {customer['Phone']} | ✉️ {customer['Email']}")
st.markdown("[🔙 Back to Customers](/1_Customers)")

st.divider()

# ---------- VISITS ----------
st.subheader("💈 Visits")
visits_df = get_visits(customer_no)
st.dataframe(visits_df, use_container_width=True)

with st.expander("➕ Add New Visit"):
    with st.form("add_visit_form"):
        visit_date = st.date_input("Visit Date", date.today())
        service = st.text_input("Service")
        total_price = st.number_input("Total Price (€)", min_value=0.0, step=0.5)
        if st.form_submit_button("Add Visit"):
            new_visit_pk = add_visit(customer_no, visit_date, service, total_price)
            if new_visit_pk:
                st.success(f"✅ Visit added successfully (VisitPK {new_visit_pk})")
                st.rerun()
            else:
                st.error("⚠️ Visit could not be added — please verify Supabase.")

st.divider()

# ---------- PRODUCTS USED ----------
st.subheader("🧴 Products Used")

if not visits_df.empty:
    visit_options = {f"{v['Date']} – {v['Service']} (ID {v['VisitID']})": v["VisitPK"] for _, v in visits_df.iterrows()}
    selected_visit_label = st.selectbox("Select Visit", list(visit_options.keys()))
    selected_visit_pk = visit_options[selected_visit_label]

    products_used_df = get_products_used(selected_visit_pk)
    st.dataframe(products_used_df, use_container_width=True)

    with st.expander("➕ Add Product Used"):
        products_df = get_products_list()
        search_term = st.text_input("Search products (name, brand, or color)")
        if search_term:
            products_df = products_df[
                products_df.apply(
                    lambda x: search_term.lower() in str(x["ProductName"]).lower()
                    or search_term.lower() in str(x["Brand"]).lower()
                    or search_term.lower() in str(x["ColorNo"]).lower(),
                    axis=1,
                )
            ]
        if products_df.empty:
            st.warning("No matching products.")
        else:
            product_names = products_df["ProductName"].tolist()
            with st.form("add_product_form"):
                selected_product = st.selectbox("Product", product_names)
                pinfo = products_df.loc[products_df["ProductName"] == selected_product].iloc[0]
                st.markdown(
                    f"**Brand:** {pinfo['Brand']}  \n"
                    f"**ColorNo:** {pinfo['ColorNo']}  \n"
                    f"**Price per g:** {pinfo['PricePerGram']} €"
                )
                weight_used = st.number_input("Weight Used (g)", min_value=0.0, step=0.5)
                if st.form_submit_button("Add Product"):
                    add_product_used(selected_visit_pk, selected_product, weight_used)
                    st.success(f"✅ Added {selected_product} to Visit {selected_visit_pk}")
                    st.rerun()
else:
    st.info("No visits yet. Add one above first.")
