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

# ---------------- DATA HELPERS ----------------

def get_customer(customer_no: int):
    """Fetch one customer by CustomerNo."""
    res = supabase.table("Customers").select("*").eq("CustomerNo", customer_no).execute()
    if not res.data:
        return None
    return pd.DataFrame(res.data).iloc[0]

def get_next_visit_number_for_customer(customer_no: int) -> int:
    """
    Get next VisitID for this customer.
    VisitID is the per-customer counter (1,2,3...).
    """
    res = supabase.table("Visits").select("VisitID").eq("CustomerNo", customer_no).order("VisitID", desc=True).limit(1).execute()
    if not res.data:
        return 1
    current_max = res.data[0].get("VisitID")
    if current_max is None:
        return 1
    return int(current_max) + 1

def get_visits(customer_no: int):
    """
    Return all visits for this customer.
    We return VisitPK (DB primary key), VisitID (human counter),
    and financial fields.
    """
    res = supabase.table("Visits").select(
        "VisitPK, VisitID, CustomerNo, Date, Service, TotalPrice_Gross, VAT, NetIncome"
    ).eq("CustomerNo", customer_no).order("Date", desc=True).execute()

    if not res.data:
        return pd.DataFrame(columns=[
            "VisitPK", "VisitID", "CustomerNo", "Date",
            "Service", "TotalPrice_Gross", "VAT", "NetIncome"
        ])
    return pd.DataFrame(res.data)

def get_products_used(visit_pk: int):
    """
    Fetch all product usage rows for a given visit (by VisitPK).
    """
    res = supabase.table("ProductsUsed").select(
        "id, VisitPK, Product, Brand, ColorNo, WeightUsed_g, ProductCost"
    ).eq("VisitPK", visit_pk).execute()

    if not res.data:
        return pd.DataFrame(columns=[
            "id", "VisitPK", "Product", "Brand", "ColorNo",
            "WeightUsed_g", "ProductCost"
        ])
    return pd.DataFrame(res.data)

def get_products_catalog():
    """
    Fetch product catalog to choose from.
    """
    res = supabase.table("Products").select(
        "ProductName, Brand, ColorNo, PricePerGram"
    ).order("Brand").execute()

    if not res.data:
        return pd.DataFrame(columns=[
            "ProductName", "Brand", "ColorNo", "PricePerGram"
        ])
    return pd.DataFrame(res.data)

def recalc_visit_netincome(visit_pk: int):
    """
    NetIncome = Gross - VAT - (SUM(ProductCost for that visit) + 2)
    """
    used_res = supabase.table("ProductsUsed").select("ProductCost").eq("VisitPK", visit_pk).execute()
    total_products_cost = 0.0
    if used_res.data:
        total_products_cost = sum([
            row.get("ProductCost", 0) or 0 for row in used_res.data
        ])

    visit_res = supabase.table("Visits").select(
        "TotalPrice_Gross, VAT"
    ).eq("VisitPK", visit_pk).execute()

    if not visit_res.data:
        return

    gross = visit_res.data[0].get("TotalPrice_Gross", 0) or 0
    vat = visit_res.data[0].get("VAT", 0) or 0

    net_income = round(gross - vat - (total_products_cost + 2), 2)

    supabase.table("Visits").update({
        "NetIncome": net_income
    }).eq("VisitPK", visit_pk).execute()

def add_visit(customer_no: int, visit_date, service: str, total_price: float):
    """
    Add new visit:
    - compute VAT
    - compute initial NetIncome
    - assign VisitID = next number for that specific customer
    - insert
    - return VisitPK (the DB primary key)
    """
    next_visit_number = get_next_visit_number_for_customer(customer_no)
    vat = round(total_price * 0.255, 2)
    initial_net = round(total_price - vat - 2, 2)

    res = supabase.table("Visits").insert({
        "CustomerNo": customer_no,
        "VisitID": next_visit_number,         # this resets per customer (1,2,3,…)
        "Date": str(visit_date),
        "Service": service,
        "TotalPrice_Gross": total_price,
        "VAT": vat,
        "NetIncome": initial_net
    }).select(
        "VisitPK"
    ).execute()

    if res.data and "VisitPK" in res.data[0]:
        return res.data[0]["VisitPK"]
    return None

def add_product_to_visit(visit_pk: int, product_name: str, weight_used: float):
    """
    Add a product usage row:
    - look up product info from catalog
    - compute ProductCost
    - insert into ProductsUsed with VisitPK
    - recalc visit NetIncome
    """
    product_lookup = supabase.table("Products").select(
        "Brand, ColorNo, PricePerGram"
    ).eq("ProductName", product_name).execute()

    if product_lookup.data:
        p = product_lookup.data[0]
        brand_val = p.get("Brand")
        color_val = p.get("ColorNo")
        price_per_g = p.get("PricePerGram", 0) or 0
        product_cost = round(weight_used * price_per_g, 2)
    else:
        brand_val = None
        color_val = None
        product_cost = 0.0

    supabase.table("ProductsUsed").insert({
        "VisitPK": visit_pk,
        "Product": product_name,
        "Brand": brand_val,
        "ColorNo": color_val,
        "WeightUsed_g": weight_used,
        "ProductCost": product_cost
    }).execute()

    recalc_visit_netincome(visit_pk)

# ---------------- PAGE RENDER ----------------

# We rely on session state set by 1_Customers.py
customer_no = st.session_state.get("selected_customer_no")

st.set_page_config(page_title="🌸 Customer Detail", layout="wide")
st.title("🌸 Customer Detail")

if not customer_no:
    st.warning("No customer selected. Please go back to the Customers page.")
    st.stop()

customer = get_customer(customer_no)
if customer is None:
    st.error(f"No customer found with number {customer_no}.")
    st.stop()

st.header(f"{customer['FullName']} (#{customer['CustomerNo']})")

phone_val = customer.get("Phone", "")
email_val = customer.get("Email", "")
st.write(f"📞 {phone_val} | ✉️ {email_val}")

if st.button("🔙 Back to Customers"):
    st.switch_page("pages/1_Customers.py")

st.divider()

# --- VISITS TABLE ---
st.subheader("💈 Visits")

visits_df = get_visits(customer_no)
st.dataframe(visits_df, use_container_width=True)

with st.expander("➕ Add New Visit"):
    with st.form("add_visit_form"):
        visit_date_val = st.date_input("Visit Date", date.today())
        service_val = st.text_input("Service")
        total_price_val = st.number_input("Total Price (€)", min_value=0.0, step=0.5)

        submit_visit = st.form_submit_button("Add Visit")
        if submit_visit:
            new_visit_pk = add_visit(
                customer_no=customer_no,
                visit_date=visit_date_val,
                service=service_val,
                total_price=total_price_val
            )
            if new_visit_pk is not None:
                st.success(f"✅ Visit added (VisitPK {new_visit_pk})")
            else:
                st.warning("Visit added, but VisitPK not returned. Refresh to see it.")
            st.rerun()

st.divider()

# --- PRODUCTS USED SECTION ---
st.subheader("🧴 Products Used")

if visits_df.empty:
    st.info("No visits yet. Add one above to record product usage.")
    st.stop()

# we only offer visits that actually have VisitPK
valid_visits = visits_df.dropna(subset=["VisitPK"]).copy()
if valid_visits.empty:
    st.warning("No visits with valid VisitPK yet. Refresh after adding a visit.")
    st.stop()

# build dropdown label list
visit_labels = []
visit_pk_values = []

for _, vrow in valid_visits.iterrows():
    visit_pk = vrow["VisitPK"]
    per_customer_id = vrow.get("VisitID", "")
    date_txt = vrow.get("Date", "")
    svc_txt = vrow.get("Service", "")
    label = f"Visit {per_customer_id} on {date_txt} – {svc_txt} (PK {visit_pk})"
    visit_labels.append(label)
    visit_pk_values.append(visit_pk)

selected_label = st.selectbox("Select Visit", visit_labels)
selected_visit_pk = visit_pk_values[visit_labels.index(selected_label)]

used_df = get_products_used(selected_visit_pk)
st.dataframe(used_df, use_container_width=True)

with st.expander("➕ Add Product Used"):
    catalog_df = get_products_catalog()

    search_term = st.text_input("Search products by name, brand, or color number")
    filtered_catalog = catalog_df.copy()

    if search_term:
        needle = search_term.lower()
        filtered_catalog = filtered_catalog[
            filtered_catalog.apply(
                lambda row: needle in str(row["ProductName"]).lower()
                or needle in str(row["Brand"]).lower()
                or needle in str(row["ColorNo"]).lower(),
                axis=1,
            )
        ]

    if filtered_catalog.empty:
        st.warning("No matching products found.")
    else:
        product_choice = st.selectbox(
            "Select Product",
            filtered_catalog["ProductName"].tolist()
        )

        info_row = filtered_catalog.loc[
            filtered_catalog["ProductName"] == product_choice
        ].iloc[0]

        st.markdown(
            f"**Brand:** {info_row.get('Brand','')}  \n"
            f"**ColorNo:** {info_row.get('ColorNo','')}  \n"
            f"**Price per g:** {info_row.get('PricePerGram','')} €"
        )

        weight_used_val = st.number_input("Weight Used (g)", min_value=0.0, step=0.5)

        if st.button("Add Product to Visit"):
            add_product_to_visit(
                visit_pk=selected_visit_pk,
                product_name=product_choice,
                weight_used=weight_used_val
            )
            st.success(f"✅ Added {product_choice} to Visit PK {selected_visit_pk}")
            st.rerun()
