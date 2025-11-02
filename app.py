import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="Salon Manager", page_icon="💇‍♀️", layout="wide")

st.title("💇‍♀️ Salon Manager Dashboard")

st.markdown("""
Welcome to **Salon Manager**!

Use the sidebar to:
- Manage customers 👩‍🦰  
- Track visits and products used 💅  
- Update service & retail product catalogs 🧴  
""")

# Simple DB check
try:
    conn = sqlite3.connect("salon.db")
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)
    st.success("✅ Connected to salon.db successfully!")
    st.dataframe(tables)
except Exception as e:
    st.error(f"Database connection failed: {e}")
finally:
    conn.close()
