import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import math
import re

# ---------------- DB ----------------
DATABASE_URL = "postgresql://parts_db_bi6b_user:vVxgefrTwrWGoHwzIPXbfemlrb4Fn6GW@dpg-d7o8oqgg4nts73aagbcg-a.oregon-postgres.render.com/parts_db_bi6b"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# ---------------- PAGE ----------------
st.set_page_config(layout="wide", page_title="Parts System")

# ---------------- COLORFUL LIGHT UI ----------------
st.markdown("""
<style>

/* Main background (soft pastel gradient) */
.stApp {
    background: linear-gradient(120deg, #fdfbfb 0%, #ebedee 100%);
    font-family: 'Segoe UI', system-ui;
    color: #1f2937;
}

/* Content card */
.block-container {
    padding: 2rem;
}

/* Sidebar gradient accent */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #ffffff, #f3f8ff);
    border-right: 1px solid #e5e7eb;
}

/* LOGO spacing */
img {
    border-radius: 10px;
}

/* Buttons - pastel gradient */
div.stButton > button {
    background: linear-gradient(90deg, #a1c4fd, #c2e9fb);
    color: #1f2937;
    border: none;
    border-radius: 10px;
    padding: 0.45rem 1rem;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    transition: 0.2s;
}

div.stButton > button:hover {
    transform: scale(1.02);
    background: linear-gradient(90deg, #c2e9fb, #a1c4fd);
}

/* Inputs */
input, textarea {
    border-radius: 8px !important;
    border: 1px solid #d1d5db !important;
}

/* HEADINGS */
h1, h2, h3 {
    font-weight: 600;
    color: #111827;
}

/* ---------------- TABLE OVERRIDE ---------------- */
div[data-testid="stDataFrame"] {
    background: linear-gradient(135deg, #ffffff, #f7fbff);
    border-radius: 12px;
    padding: 10px;
    box-shadow: 0 3px 12px rgba(0,0,0,0.05);
}

/* Table header feel */
thead tr th {
    background: linear-gradient(90deg, #dbeafe, #eff6ff) !important;
    color: #1e3a8a !important;
    font-weight: 600;
}

/* Table rows hover effect */
tbody tr:hover {
    background: #f0f9ff !important;
    transition: 0.2s;
}

</style>
""", unsafe_allow_html=True)

# ---------------- TABLES ----------------
cur.execute("""
CREATE TABLE IF NOT EXISTS parts_table (
    id SERIAL PRIMARY KEY,
    part_no TEXT,
    brand TEXT,
    price NUMERIC,
    description TEXT,
    moq INTEGER
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT
);
""")

cur.execute("""
INSERT INTO users (username, password)
SELECT 'admin','admin'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username='admin');
""")

conn.commit()

# ---------------- CACHE ----------------
@st.cache_data
def load_parts():
    df = pd.read_sql("SELECT * FROM parts_table", conn)
    df.columns = df.columns.str.lower()
    return df

# ---------------- SESSION ----------------
if "table_data" not in st.session_state:
    st.session_state.table_data = pd.DataFrame(
        columns=["Brand","Part No","Description","Qty","Price","Amount"]
    )

if "input_table" not in st.session_state:
    st.session_state.input_table = pd.DataFrame(
        columns=["Brand","Part No","Qty"]
    )

if "user" not in st.session_state:
    st.session_state.user = None

# ---------------- LOGIN ----------------
def login(u,p):
    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s",(u,p))
    return cur.fetchone()

if st.session_state.user is None:

    col1, col2, col3 = st.columns([1,2,1])

    with col2:
        st.image("logo.png", width=180)

        st.markdown("### Welcome Back")

        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Login"):
            if login(u,p):
                st.session_state.user = {"username":u}
                st.rerun()
            else:
                st.error("Invalid credentials")

    st.stop()

username = st.session_state.user["username"]

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.image("logo.png", width=140)
    st.markdown(f"### 👤 {username}")

    pages = ["📊 Price Lookup"]
    if username == "admin":
        pages += ["📤 Upload Data", "🛠 Admin Panel"]

    page = st.radio("Navigation", pages)

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# ---------------- HELPERS ----------------
def norm(x):
    if pd.isna(x):
        return ""
    x = str(x).lower().strip()
    x = re.sub(r'[^a-z0-9]', '', x)
    x = x.lstrip('0')
    return x

def safe_float(v):
    try:
        if pd.isna(v): return 0
        return float(v)
    except:
        return 0

def safe_int(v):
    try:
        return int(float(v))
    except:
        return 0

# ================= PRICE LOOKUP =================
if page == "📊 Price Lookup":

    st.title("📊 Price Lookup")

    db_df = load_parts()

    if db_df.empty:
        st.warning("No data found")
        st.stop()

    db_df["brand"] = db_df["brand"].astype(str).str.strip()
    brand_list = sorted(db_df["brand"].unique())

    db_df["part_norm"] = db_df["part_no"].apply(norm)
    db_df["brand_norm"] = db_df["brand"].apply(norm)

    col1, col2 = st.columns([10,1])
    with col2:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    input_df = st.data_editor(
        st.session_state.input_table,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Brand": st.column_config.SelectboxColumn("Brand", options=brand_list)
        }
    )

    if st.button("🔎 Fetch Prices"):

        result = []

        for _, r in input_df.iterrows():

            part = norm(r.get("Part No"))
            brand = norm(r.get("Brand"))

            qty = pd.to_numeric(r.get("Qty"), errors="coerce")
            if pd.isna(qty) or qty<=0:
                qty = 1

            match = db_df[
                (db_df["part_norm"] == part) &
                (db_df["brand_norm"] == brand)
            ]

            if not match.empty:
                row = match.iloc[0]
                price = safe_float(row["price"])
                desc = row.get("description","N/A")
            else:
                price = 0
                desc = "Not Found"

            result.append({
                "Brand": r.get("Brand"),
                "Part No": r.get("Part No"),
                "Description": desc,
                "Qty": qty,
                "Price": price,
                "Amount": qty * price
            })

        st.session_state.table_data = pd.DataFrame(result)

    df = st.session_state.table_data.copy()
    df["Amount"] = df["Qty"] * df["Price"]

    st.dataframe(df, use_container_width=True)
    st.success(f"Total: € {df['Amount'].sum():.2f}")
