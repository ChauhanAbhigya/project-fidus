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

# ---------------- SAFE FUNCTION (IMPORTANT FIX) ----------------
def safe(v):
    if v is None:
        return 0
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return 0
    if pd.isna(v):
        return 0
    return v

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
    res = supabase.table("users")\
        .select("*")\
        .eq("username", u.strip())\
        .eq("password", p.strip())\
        .execute()
    return res.data[0] if res.data else None

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
    st.markdown("<div class='main-title'>📊 Price Lookup System</div>", unsafe_allow_html=True)

# ---------------- NORMALIZER ----------------
def norm(x):
    if pd.isna(x):
        return ""
    return str(x).strip().lower().replace(".0","").replace(" ","").replace("-","").replace("/","")

# ========================= PRICE PAGE =========================
if page == "📊 Price Lookup":

    col_title, col_refresh = st.columns([10, 1])

    with col_refresh:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    db_df = load_parts()

    if db_df.empty:
        st.warning("⚠ No data found")
        st.stop()

    db_df["part_no"] = db_df["part_no"].astype(str).apply(norm)
    db_df["brand"] = db_df["brand"].astype(str).str.strip().str.lower()

    brand_list = sorted(db_df["brand"].unique())

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

            part = norm(row.get("Part No"))
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
                desc = "Not Found"

            result.append({
                "Brand": row.get("Brand"),
                "Part No": row.get("Part No"),
                "Description": desc,
                "Qty": qty,
                "Price": price,
                "Amount": qty * price
            })

        st.session_state.table_data = pd.DataFrame(result)
        st.success("Fetched Successfully")

    df = st.session_state.table_data.copy()

    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
    df["Amount"] = df["Qty"] * df["Price"]

    st.dataframe(df, use_container_width=True)
    st.markdown(f"### 💰 Total: € {df['Amount'].sum():.2f}")

    if st.button("💾 Save Offer"):

        clean_rows = []

        for _, row in df.iterrows():
            clean_rows.append({
                "username": username,
                "brand": safe(row["Brand"]),
                "part_no": safe(row["Part No"]),
                "qty": float(safe(row["Qty"])),
                "price": float(safe(row["Price"])),
                "amount": float(safe(row["Amount"]))
            })

        supabase.table("offer_items").insert(clean_rows).execute()
        st.success("Saved")

# ========================= UPLOAD PAGE =========================
elif page == "📤 Upload Data" and username == "admin":

    st.title("Upload Excel Data")

    files = st.file_uploader("Upload", type=["xlsx"], accept_multiple_files=True)

    if files:

        total = 0
        progress = st.progress(0)

        for i, f in enumerate(files):

            df = pd.read_excel(f)

            df.columns = df.columns.str.strip().str.lower()

            df.rename(columns={
                "part no": "part_no",
                "price [eur]": "price",
                "item description": "description",
                "moq": "moq"
            }, inplace=True)

            for col in ["part_no","brand","price","description"]:
                if col not in df.columns:
                    df[col] = ""

            df["part_no"] = df["part_no"].apply(norm)
            df["brand"] = df["brand"].astype(str).str.lower().str.strip()
            df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

            df = df.replace([float("inf"), -float("inf")], 0)
            df = df.fillna(0)

            clean_data = []

            for r in df.to_dict("records"):
                clean_data.append({k: safe(v) for k, v in r.items()})

            supabase.table("parts_table_v2").insert(clean_data).execute()

            total += len(clean_data)
            progress.progress((i+1)/len(files))

        st.success(f"Uploaded {total}")
        st.cache_data.clear()
        st.rerun()

# ========================= ADMIN PANEL =========================
elif page == "🛠 Admin Panel" and username == "admin":

    st.subheader("Admin Panel")

    u = st.text_input("User")
    p = st.text_input("Pass")

    if st.button("Add"):
        supabase.table("users").insert({
            "username": u,
            "password": p
        }).execute()

        st.success("Added")

    users = supabase.table("users").select("username").execute().data
    user_list = [x["username"] for x in users if x["username"] != "admin"]

    if user_list:
        sel = st.selectbox("Select User", user_list)

        if st.button("Delete"):
            supabase.table("users").delete().eq("username", sel).execute()
            st.success("Deleted")
