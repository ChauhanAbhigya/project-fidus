from supabase import create_client
import streamlit as st
import pandas as pd
import os
import math

st.set_page_config(layout="wide")

# ---------------- 🔐 SUPABASE CONFIG (NEW) ----------------
st.sidebar.markdown("### 🔗 Supabase Config")

default_url = os.getenv("https://eicwssbhjfvekaerjljm.supabase.co", "")
default_key = os.getenv("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVpY3dzc2JoamZ2ZWthZXJqbGptIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcyNzI1NTUsImV4cCI6MjA5Mjg0ODU1NX0.okPnbQrcKN6A2-Xj_99TgB47mtx9H6KO20asriBA19g", "")

SUPABASE_URL = st.sidebar.text_input("Supabase URL", value=default_url)
SUPABASE_KEY = st.sidebar.text_input("Supabase Key", value=default_key, type="password")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.warning("Please enter Supabase URL and Key in sidebar")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- UI ----------------
st.markdown("""
<style>
body {
    background: linear-gradient(135deg, #f7faff, #eef3ff);
}
.main-title {
    font-size: 32px;
    font-weight: 700;
    color: #1a237e;
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

    st.markdown("""
    <style>
    .login-box {
        width: 380px;
        margin: auto;
        margin-top: 120px;
        padding: 30px;
        background: white;
        border-radius: 12px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.08);
        text-align: center;
    }
    .login-title {
        font-size: 24px;
        font-weight: 600;
        margin-bottom: 20px;
        color: #1a237e;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    st.markdown("<div class='login-title'>🔐 Secure Login</div>", unsafe_allow_html=True)

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

def safe(v, is_int=False):
    try:
        if v is None:
            return None
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return int(float(v)) if is_int else float(v)
    except:
        return v

# ---------------- PRICE PAGE ----------------
if page == "📊 Price Lookup":

    db_df = load_parts()

    if db_df.empty:
        st.warning("No data found")
        st.stop()

    db_df["part_no"] = db_df["part_no"].astype(str).apply(norm)
    db_df["brand"] = db_df["brand"].astype(str).str.lower()

    brand_list = sorted(db_df["brand"].dropna().unique())

    input_df = st.data_editor(
        st.session_state.input_table,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Brand": st.column_config.SelectboxColumn("Brand", options=brand_list),
            "Part No": st.column_config.TextColumn("Part No"),
            "Qty": st.column_config.NumberColumn("Qty", min_value=1, step=1)
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

        st.session_state.input_table = pd.DataFrame(
            columns=["Brand","Part No","Qty"]
        )

        st.success("Prices fetched successfully")

    df = st.session_state.table_data

    if not df.empty:

        df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
        df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
        df["Amount"] = df["Qty"] * df["Price"]

        st.dataframe(df, use_container_width=True)

        st.markdown(f"### 💰 Total: € {df['Amount'].sum():.2f}")

    if st.button("💾 Save Offer"):

        if df.empty:
            st.warning("No data to save")
        else:
            records = []

            for _, r in df.iterrows():
                records.append({
                    "username": username,
                    "brand": r["Brand"],
                    "part_no": r["Part No"],
                    "qty": safe(r["Qty"], True),
                    "price": safe(r["Price"]),
                    "amount": safe(r["Amount"])
                })

            for i in range(0, len(records), 200):
                supabase.table("offer_items").insert(records[i:i+200]).execute()

            st.success("Saved successfully")

# ---------------- UPLOAD ----------------
elif page == "📤 Upload Data" and username == "admin":

    uploaded = st.file_uploader("Upload Excel", type=["xlsx"])

    if uploaded:

        df = pd.read_excel(uploaded, dtype=str)

        df.columns = df.columns.str.strip().str.lower()
        df = df.rename(columns={
            "part no": "part_no",
            "brand": "brand",
            "price": "price",
            "description": "description"
        })

        df["part_no"] = df["part_no"].astype(str).apply(norm)
        df["brand"] = df["brand"].astype(str).str.lower()
        df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

        data = df.to_dict(orient="records")

        for i in range(0, len(data), 200):
            supabase.table("parts_table").insert(data[i:i+200]).execute()

        st.success(f"Uploaded {len(data)} rows")

        st.cache_data.clear()
        st.rerun()

# ---------------- ADMIN ----------------
elif page == "🛠 Admin Panel" and username == "admin":

    st.subheader("Admin Panel")

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
