import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client, Client

st.set_page_config(page_title="Customer Detail", layout="wide")

# ---------- SUPABASE CONNECTION ----------
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

def update_customer(customer_no, name, phone, email, notes):
    supabase.table("Customers").update({
        "FullName": name,
        "Phone": phone,
        "Email": email,
        "Notes": notes
    }).eq("CustomerNo", customer_no).execute()

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
    vat = round(total_price-(total_price/1.255), 2)
    net_income = round(total_price - vat - 2, 2)
    existing = supabase.table("Visits").select("VisitID").eq("CustomerNo", customer_no).order("VisitID", desc=True).limit(1).execute()
    next_visit_id = existing.data[0]["VisitID"] + 1 if existing.data else 1
    res = supabase.table("Visits").insert({
        "CustomerNo": customer_no,
        "VisitID": next_visit_id,
        "Date": str(visit_date),
        "Service": service,
        "TotalPrice_Gross": total_price,
        "VAT": vat,
        "NetIncome": net_income
    }).execute()
    return res.data[0]["VisitPK"] if res.data else None

def add_product_used(visit_pk, product_name, weight_used):
    pinfo = supabase.table("Products").select("Brand, ColorNo, PricePerGram").eq("ProductName", product_name).execute()
    if pinfo.data:
        brand = pinfo.data[0]["Brand"]
        color = pinfo.data[0]["ColorNo"]
        price = float(pinfo.data[0]["PricePerGram"])
        cost = round(weight_used * price, 2)
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

    used = supabase.table("ProductsUsed").select("ProductCost").eq("VisitPK", visit_pk).execute()
    total_cost = sum(float(p["ProductCost"]) for p in used.data)
    visit = supabase.table("Visits").select("TotalPrice_Gross, VAT").eq("VisitPK", visit_pk).execute()
    if visit.data:
        gross = float(visit.data[0]["TotalPrice_Gross"])
        vat = float(visit.data[0]["VAT"])
        new_net = round(gross - vat - total_cost - 2, 2)
        supabase.table("Visits").update({"NetIncome": new_net}).eq("VisitPK", visit_pk).execute()

# ---------- PAGE BODY ----------
st.title("🌸 Customer Detail")

customer_no = st.session_state.get("selected_customer_no")
if not customer_no:
    st.warning("No customer selected. Please go back to the Customers page.")
    st.stop()

customer = get_customer(customer_no)
if not customer:
    st.error(f"No customer found with number {customer_no}.")
    st.stop()

st.header(f"{customer['FullName']} (#{customer['CustomerNo']})")

# ---------- CONTACT INFO & EDIT ----------
with st.expander("✏️ Edit Customer Info"):
    with st.form("edit_customer_form"):
        new_name = st.text_input("Full Name", customer["FullName"])
        new_phone = st.text_input("Phone", customer["Phone"])
        new_email = st.text_input("Email", customer["Email"])
        new_notes = st.text_area("Notes", customer.get("Notes", ""))
        if st.form_submit_button("Save Changes"):
            update_customer(customer_no, new_name, new_phone, new_email, new_notes)
            st.success("✅ Customer Updated")
            st.rerun()

st.write(f"📞 {customer['Phone']} | ✉️ {customer['Email']}")

if st.button("🔙 Back to Customers"):
    st.switch_page("pages/1_Customers.py")

st.divider()

# ---------- PRICE VISIBILITY TOGGLE ----------
show_prices = st.checkbox("💶 Show Price Details", value=True)

# ---------- VISITS ----------
st.subheader("💈 Visits")
visits = get_visits(customer_no)

if not show_prices:
    visits = visits.drop(columns=["TotalPrice_Gross", "VAT", "NetIncome"], errors="ignore")

st.dataframe(visits, use_container_width=True)

with st.expander("➕ Add New Visit"):
    with st.form("add_visit_form"):
        visit_date = st.date_input("Visit Date", date.today())
        service = st.text_input("Service")
        total_price = st.number_input("Total Price (€)", min_value=0.0, step=0.5)
        if st.form_submit_button("Add Visit"):
            new_pk = add_visit(customer_no, visit_date, service, total_price)
            if new_pk:
                st.success("✅ Visit added!")
                st.rerun()

st.divider()

# ---------- PRODUCTS USED ----------
st.subheader("🧴 Products Used")

if not visits.empty:
    visit_options = {f"{v['Date']} – {v['Service']} (ID {v['VisitID']})": v["VisitPK"] for _, v in visits.iterrows()}
    selected_visit_label = st.selectbox("Select Visit", list(visit_options.keys()))
    selected_visit_pk = visit_options[selected_visit_label]

    products_used = get_products_used(selected_visit_pk)

    if not show_prices:
        products_used = products_used.drop(columns=["ProductCost"], errors="ignore")

    st.dataframe(products_used, use_container_width=True)

    with st.expander("➕ Add Product Used"):
        products_df = get_products_list()
        search_term = st.text_input("Search product")
        if search_term:
            products_df = products_df[
                products_df.apply(
                    lambda x: search_term.lower() in str(x["ProductName"]).lower()
                    or search_term.lower() in str(x["Brand"]).lower()
                    or search_term.lower() in str(x["ColorNo"]).lower(),
                    axis=1
                )
            ]
        if products_df.empty:
            st.warning("No products found.")
        else:
            product_names = products_df["ProductName"].tolist()
            with st.form("add_product_form"):
                selected_product = st.selectbox("Product", product_names)
                pinfo = products_df.loc[products_df["ProductName"] == selected_product].iloc[0]
                st.markdown(
                    f"**Brand:** {pinfo['Brand']}  \n"
                    f"**ColorNo:** {pinfo['ColorNo']}  \n"
                    f"**Price/g:** {pinfo['PricePerGram']} €"
                )
                weight_used = st.number_input("Weight Used (g)", min_value=0.0, step=0.5)
                if st.form_submit_button("Add Product"):
                    add_product_used(selected_visit_pk, selected_product, weight_used)
                    st.success(f"✅ Added {selected_product}")
                    st.rerun()
else:
    st.info("No visits yet.")
