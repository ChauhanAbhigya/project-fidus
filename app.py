from supabase import create_client
import streamlit as st
import pandas as pd
import os
import math

# ---------------- SUPABASE ----------------
SUPABASE_URL = "https://eicwssbhjfvekaerjljm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVpY3dzc2JoamZ2ZWthZXJqbGptIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcyNzI1NTUsImV4cCI6MjA5Mjg0ODU1NX0.okPnbQrcKN6A2-Xj_99TgB47mtx9H6KO20asriBA19g"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(layout="wide")

# ---------------- PREMIUM LIGHT UI ----------------
st.markdown("""
<style>
body {
    background: linear-gradient(135deg, #eef2ff, #fdf2f8);
}
.block-container {
    background: linear-gradient(135deg, #ffffff, #f8fafc);
    padding: 20px;
    border-radius: 16px;
    box-shadow: 0 6px 25px rgba(0,0,0,0.05);
}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #6366f1, #818cf8);
}
section[data-testid="stSidebar"] * {
    color: white !important;
}
.main-title {
    font-size: 34px;
    font-weight: 700;
    color: #1e293b;
}
.login-box {
    width: 400px;
    margin: auto;
    margin-top: 120px;
    padding: 35px;
    background: linear-gradient(135deg, #ffffff, #eef2ff);
    border-radius: 16px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.08);
    text-align: center;
}
.stButton>button {
    background: linear-gradient(90deg, #6366f1, #3b82f6);
    color: white;
    border-radius: 8px;
    height: 40px;
}
</style>
""", unsafe_allow_html=True)

# ---------------- CACHE ----------------
@st.cache_data(ttl=0)
def load_parts():
    try:
        data = supabase.table("parts_table").select("*").execute()
        return pd.DataFrame(data.data or [])
    except:
        return pd.DataFrame()

# 🔥 NEW: ALWAYS FRESH BRANDS (NO CACHE)
def load_brands():
    try:
        data = supabase.table("parts_table").select("brand").execute()
        df = pd.DataFrame(data.data or [])
        if df.empty:
            return []
        return sorted(set(df["brand"].astype(str).str.strip().str.lower()))
    except:
        return []

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
def login(u, p):
    res = supabase.table("users")\
        .select("*")\
        .eq("username", u.strip())\
        .eq("password", p.strip())\
        .execute()
    return res.data[0] if res.data else None

if st.session_state.user is None:

    st.markdown("<div class='login-box'>", unsafe_allow_html=True)

    if os.path.exists("logo.png"):
        st.image("logo.png", width=130)

    st.markdown("### 🔐 Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login", use_container_width=True):
        user = login(u, p)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Invalid username or password")

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

user = st.session_state.user
username = user["username"]

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown(f"👤 Logged in: **{username}**")

    pages = ["📊 Price Lookup"]
    if username == "admin":
        pages += ["📤 Upload Data", "🛠 Admin Panel"]

    page = st.radio("Menu", pages)

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# ---------------- HEADER ----------------
st.markdown("<div class='main-title'>📊 Price Lookup System</div>", unsafe_allow_html=True)

# ---------------- HELPERS ----------------
def norm(x):
    if pd.isna(x):
        return ""
    return str(x).replace(".0","").replace(" ","").replace("-","").replace("/","").strip().lower()

# ---------------- PRICE PAGE ----------------
if page == "📊 Price Lookup":

    col1, col2 = st.columns([6,1])
    with col2:
        if st.button("🔄 Refresh"):
            load_parts.clear()
            st.cache_data.clear()
            st.rerun()

    db_df = load_parts()

    if db_df.empty:
        st.warning("No data found")
        st.stop()

    db_df["part_no"] = db_df["part_no"].astype(str).apply(norm)
    db_df["brand"] = db_df["brand"].astype(str).str.strip().str.lower()

    # 🔥 FIXED BRAND DROPDOWN
    brand_list = load_brands()

    input_df = st.data_editor(
        st.session_state.input_table,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Brand": st.column_config.SelectboxColumn("Brand", options=brand_list)
        },
        key="input_editor"
    )

    if st.button("🔎 Fetch Prices"):

        result = []

        for _, r in input_df.iterrows():
            part = norm(r.get("Part No"))
            brand = str(r.get("Brand","")).lower()
            qty = pd.to_numeric(r.get("Qty"), errors="coerce")

            if pd.isna(qty) or qty <= 0:
                qty = 1

            match = db_df[
                (db_df["part_no"] == part) &
                (db_df["brand"] == brand)
            ]

            if not match.empty:
                row = match.iloc[0]
                price = float(row.get("price",0))
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

    if not df.empty:
        df["Amount"] = df["Qty"] * df["Price"]
        st.dataframe(df, use_container_width=True)
        st.markdown(f"### 💰 Total: € {df['Amount'].sum():.2f}")

# ---------------- UPLOAD ----------------
elif page == "📤 Upload Data" and username == "admin":

    uploaded = st.file_uploader("Upload Excel", type=["xlsx"])

    if uploaded:

        df = pd.read_excel(uploaded, dtype=str)
        df.columns = df.columns.str.strip().str.lower()

        df = df.rename(columns={
            "part no": "part_no",
            "brand": "brand",
            "price [eur]": "price",
            "item description": "description",
            "moq": "moq"
        })

        df["part_no"] = df["part_no"].astype(str).str.strip()
        df["brand"] = df["brand"].astype(str).str.strip().str.lower()
        df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

        data = df.to_dict(orient="records")

        clean_data = []
        for row in data:
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, float) and (pd.isna(v) or v == float("inf") or v == float("-inf")):
                    clean_row[k] = None
                else:
                    clean_row[k] = v
            clean_data.append(clean_row)

        for i in range(0, len(clean_data), 200):
            supabase.table("parts_table").insert(clean_data[i:i+200]).execute()

        st.success(f"Uploaded {len(clean_data)} rows")

        load_parts.clear()
        st.cache_data.clear()
        st.rerun()

# ---------------- ADMIN ----------------
elif page == "🛠 Admin Panel" and username == "admin":

    u = st.text_input("New user")
    p = st.text_input("Password", type="password")

    if st.button("Add User"):
        supabase.table("users").insert({
            "username": u,
            "password": p
        }).execute()
        st.success("User added")

    users = supabase.table("users").select("username").execute().data
    st.write([x["username"] for x in users])
