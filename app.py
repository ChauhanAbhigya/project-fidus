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

# ---------------- CACHE ----------------
@st.cache_data(ttl=0)
def load_parts():
    try:
        data = supabase.table("parts_table_v2").select("*").execute()
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

# ---------------- LOGIN ----------------
if "user" not in st.session_state:
    st.session_state.user = None

def login(u, p):
    try:
        res = supabase.table("users")\
            .select("*")\
            .eq("username", u.strip())\
            .eq("password", p.strip())\
            .execute()
        return res.data[0] if res.data else None
    except:
        return None

if st.session_state.user is None:
    st.title("🔐 Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login(u, p)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Invalid username or password")
    st.stop()

user = st.session_state.user
username = user["username"]

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown(f"👤 Logged in as: **{username}**")

    pages = ["📊 Price Lookup"]
    if username == "admin":
        pages.append("📤 Upload Data")
        pages.append("🛠 Admin Panel")

    page = st.radio("Menu", pages)

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# ---------------- HEADER ----------------
col1, col2 = st.columns([1,7])

with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=100)

with col2:
    st.markdown("<h2>📊 Price Lookup System</h2>", unsafe_allow_html=True)

# ========================= SAFE NORMALIZER =========================
def norm(x):
    if pd.isna(x):
        return ""
    return (
        str(x)
        .replace(".0","")
        .replace(" ","")
        .replace("-","")
        .replace("/","")
        .lstrip("0")
        .strip()
        .lower()
    )

# ========================= UNIVERSAL CLEANER =========================
def clean_excel(df):
    df.columns = df.columns.str.strip().str.lower()

    col_map = {
        "part no": "part_no",
        "part number": "part_no",
        "partno": "part_no",

        "brand": "brand",

        "price": "price",
        "price [eur]": "price",

        "item description": "description",
        "description": "description",

        "moq": "moq"
    }

    df.rename(columns=col_map, inplace=True)

    for col in ["part_no", "brand", "price", "description"]:
        if col not in df.columns:
            df[col] = None

    df["part_no"] = df["part_no"].astype(str).apply(norm)
    df["brand"] = df["brand"].astype(str).str.strip().str.lower()
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

    df = df.dropna(subset=["part_no", "brand"])

    df = df.replace([float("inf"), -float("inf")], None)
    df = df.where(pd.notnull(df), None)

    return df

# ========================= PRICE PAGE =========================
if page == "📊 Price Lookup":

    col1, col2 = st.columns([10,1])

    with col2:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    db_df = load_parts()

    if db_df.empty:
        st.warning("⚠ No data found")
        st.stop()

    # FIX DB CLEANING
    db_df["part_no"] = db_df["part_no"].astype(str).apply(norm)
    db_df["brand"] = db_df["brand"].astype(str).str.strip().str.lower()

    if "price" not in db_df.columns:
        db_df["price"] = 0

    if "description" not in db_df.columns:
        db_df["description"] = "N/A"

    brand_list = sorted(db_df["brand"].dropna().unique())

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

        for _, row in input_df.iterrows():

            part = norm(row.get("Part No",""))
            brand = str(row.get("Brand","")).strip().lower()
            qty = pd.to_numeric(row.get("Qty"), errors="coerce")

            if not part:
                continue

            if pd.isna(qty) or qty <= 0:
                qty = 1

            match = db_df[
                (db_df["part_no"] == part) &
                (db_df["brand"] == brand)
            ]

            if not match.empty:
                r = match.iloc[0]
                price = float(r.get("price", 0))
                desc = r.get("description", "N/A")
            else:
                price = 0
                desc = "Item not found"

            result.append({
                "Brand": row.get("Brand"),
                "Part No": row.get("Part No"),
                "Description": desc,
                "Qty": qty,
                "Price": price,
                "Amount": qty * price
            })

        st.session_state.table_data = pd.DataFrame(result)
        st.success("Prices fetched")

    df = st.session_state.table_data.copy()

    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
    df["Amount"] = df["Qty"] * df["Price"]

    st.dataframe(df, use_container_width=True)
    st.markdown(f"### 💰 Total: € {df['Amount'].sum():.2f}")

    if st.button("💾 Save Offer"):

        for _, row in df.iterrows():

            supabase.table("offer_items").insert({
                "username": username,
                "brand": row["Brand"],
                "part_no": row["Part No"],
                "qty": float(row["Qty"] or 0),
                "price": float(row["Price"] or 0),
                "amount": float(row["Amount"] or 0)
            }).execute()

        st.success("Saved successfully")

# ========================= UPLOAD PAGE =========================
elif page == "📤 Upload Data" and username == "admin":

    st.title("📤 Upload Excel Data")

    uploaded_files = st.file_uploader(
        "Upload Excel Files",
        type=["xlsx"],
        accept_multiple_files=True
    )

    if uploaded_files:

        total = 0
        progress = st.progress(0)

        for i, f in enumerate(uploaded_files):

            df = pd.read_excel(f, dtype=str)
            df = clean_excel(df)

            supabase.table("parts_table_v2").insert(
                df.to_dict(orient="records")
            ).execute()

            total += len(df)
            progress.progress((i+1)/len(uploaded_files))

        st.success(f"Uploaded {total} rows")
        st.cache_data.clear()
        st.rerun()

# ========================= ADMIN =========================
elif page == "🛠 Admin Panel" and username == "admin":

    st.subheader("Admin Panel")

    u = st.text_input("New Username")
    p = st.text_input("Password", type="password")

    if st.button("Add User"):
        supabase.table("users").insert({
            "username": u,
            "password": p
        }).execute()
        st.success("User added")

    users = supabase.table("users").select("username").execute().data or []
    users = [x["username"] for x in users if x["username"] != "admin"]

    if users:
        sel = st.selectbox("Delete User", users)

        if st.button("Delete User"):
            supabase.table("users").delete().eq("username", sel).execute()
            st.success("Deleted")
