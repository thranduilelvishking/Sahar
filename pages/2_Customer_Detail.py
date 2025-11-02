import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import date

# ---------------- PAGE SETUP ----------------
st.set_page_config(page_title="🌸 Customer Detail", layout="wide")

# ---------------- SUPABASE CONNECTION ----------------
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

# ---------------- HELPERS ----------------
def get_customer(customer_no):
    res = supabase.table("Customers").select("*").eq("CustomerNo", customer_no).execute()
    return pd.DataFrame(res.data).iloc[0] if res.data else None

def get_visits(customer_no):
    res = supabase.table("Visits").select("*").eq("CustomerNo", customer_no).order("Date", desc=True).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def get_products_used(visit_id):
    res = supabase.table("ProductsUsed").select("*").eq("VisitID", visit_id).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def get_products_list():
    res = supabase.table("Products").select("ProductName, Brand, ColorNo, PricePerGram").order("Brand").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def add_visit(customer_no, visit_date, service, total_price):
    vat = round(total_price * 0.255, 2)
    net = round(total_price - vat - 2, 2)
    supabase.table("Visits").insert({
        "CustomerNo": customer_no,
        "Date": str(visit_date),
        "Service": service,
        "TotalPrice_Gross": total_price,
        "VAT": vat,
        "NetIncome": net
    }).execute()

def add_product_used(visit_id, product_name, weight_used):
    products = supabase.table("Products").select("*").eq("ProductName", product_name).execute()
    if products.data:
        p = products.data[0]
        cost = round(weight_used * p["PricePerGram"], 2)
        supabase.table("ProductsUsed").insert({
            "VisitID": visit_id,
            "Product": product_name,
            "Brand": p["Brand"],
            "ColorNo": p["ColorNo"],
            "WeightUsed_g": weight_used,
            "ProductCost": cost
        }).execute()

        # Update Visit net income
        used = supabase.table("ProductsUsed").select("ProductCost").eq("VisitID", visit_id).execute()
        total_used = sum([u["ProductCost"] for u in used.data]) if used.data else 0
        visits = supabase.table("Visits").select("TotalPrice_Gross, VAT").eq("VisitID", visit_id).execute()
        if visits.data:
            v = visits.data[0]
            net = round(v["TotalPrice_Gross"] - v["VAT"] - total_used - 2, 2)
            supabase.table("Visits").update({"NetIncome": net}).eq("VisitID", visit_id).execute()

# ---------------- PAGE BODY ----------------
customer_no = st.session_state.get("selected_customer_no")

if not customer_no:
    st.warning("No customer selected. Please go back to the Customers page.")
    st.stop()

customer = get_customer(customer_no)
if customer is None:
    st.error(f"No customer found with number {customer_no}.")
    st.stop()

st.title(f"🌸 {customer['FullName']} (#{customer['CustomerNo']})")
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
        if st.form_submit_button("Add Visit"):
            add_visit(customer_no, visit_date, service, total_price)
            st.success("✅ Visit added successfully!")
            st.rerun()

st.divider()

# ---------- PRODUCTS USED ----------
st.subheader("🧴 Products Used")
if not visits.empty:
    visit_options = {
        f"{v['Date']} – {v['Service']} (ID {v['VisitID']})": v["VisitID"]
        for _, v in visits.iterrows()
    }
    selected_visit_label = st.selectbox("Select Visit", list(visit_options.keys()))
    selected_visit_id = visit_options[selected_visit_label]

    products_used = get_products_used(selected_visit_id)
    st.dataframe(products_used, use_container_width=True)

    with st.expander("➕ Add Product Used"):
        products_df = get_products_list()
        search_term = st.text_input("Search products by name, brand, or color number")
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
            st.warning("No matching products found.")
        else:
            selected_product = st.selectbox("Select Product", products_df["ProductName"])
            pinfo = products_df.loc[products_df["ProductName"] == selected_product].iloc[0]
            st.markdown(
                f"**Brand:** {pinfo['Brand']}  \n**ColorNo:** {pinfo['ColorNo']}  \n**Price/g:** {pinfo['PricePerGram']} €"
            )
            weight_used = st.number_input("Weight Used (g)", min_value=0.0, step=0.5)
            if st.button("Add Product"):
                add_product_used(selected_visit_id, selected_product, weight_used)
                st.success(f"✅ Added {selected_product} to Visit {selected_visit_id}")
                st.rerun()
else:
    st.info("No visits yet. Add one above to record product usage.")
