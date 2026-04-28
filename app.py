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
@st.cache_data
def load_parts():
    data = supabase.table("parts_table").select("*").execute()
    df = pd.DataFrame(data.data or [])
    df.columns = df.columns.str.lower()   # 🔥 FIX
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
            st.error("Invalid credentials")

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
st.title("📊 Price Lookup System")

# ---------------- HELPERS ----------------
def norm(x):
    if pd.isna(x):
        return ""
    return str(x).replace(".0","").replace(" ","").replace("-","").replace("/","").strip().lower()

def safe_float(v):
    try:
        if v is None or (isinstance(v,float) and (math.isnan(v) or math.isinf(v))):
            return 0.0
        return float(v)
    except:
        return 0.0

def safe_int(v):
    try:
        return int(float(v))
    except:
        return 0

# ================= PRICE LOOKUP =================
if page == "📊 Price Lookup":

    db_df = load_parts()

    if db_df.empty:
        st.warning("No data found")
        st.stop()

    # 🔥 CLEAN BRAND
    db_df["brand"] = db_df["brand"].astype(str).str.strip()
    db_df = db_df[db_df["brand"] != ""]

    brand_list = sorted(db_df["brand"].unique().tolist())

    # 🔥 REFRESH BUTTON
    col1, col2 = st.columns([10,1])
    with col2:
        if st.button("🔄"):
            st.cache_data.clear()
            st.rerun()

    input_df = st.data_editor(
        st.session_state.input_table,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Brand": st.column_config.SelectboxColumn(
                "Brand",
                options=brand_list
            )
        },
        key="input_editor"
    )

    if st.button("🔎 Fetch Prices"):

        result = []

        for _, r in input_df.iterrows():

            part = norm(r.get("Part No"))
            brand = str(r.get("Brand","")).strip()

            qty = pd.to_numeric(r.get("Qty"), errors="coerce")
            if pd.isna(qty) or qty <= 0:
                qty = 1

            match = db_df[
                (db_df["part_no"].astype(str).apply(norm) == part) &
                (db_df["brand"].str.lower() == brand.lower())
            ]

            if not match.empty:
                row = match.iloc[0]
                price = safe_float(row.get("price"))
                desc = row.get("description","N/A")
            else:
                price = 0
                desc = "Not Found"

            result.append({
                "Brand": brand,
                "Part No": r.get("Part No"),
                "Description": desc,
                "Qty": qty,
                "Price": price,
                "Amount": qty * price
            })

        st.session_state.table_data = pd.DataFrame(result)

    df = st.session_state.table_data.copy()

    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
    df["Amount"] = df["Qty"] * df["Price"]

    st.dataframe(df, use_container_width=True)

    st.markdown(f"### 💰 Total: € {df['Amount'].sum():.2f}")

# ================= UPLOAD =================
elif page == "📤 Upload Data":

    uploaded = st.file_uploader("Upload Excel", type=["xlsx"], accept_multiple_files=True)

    if uploaded:
        total = 0

        for f in uploaded:

            df = pd.read_excel(f)
            df.columns = df.columns.str.strip().str.lower()

            # 🔥 UNIVERSAL COLUMN MAP
            col_map = {
                "part no": "part_no",
                "part number": "part_no",
                "price [eur]": "price",
                "item description": "description"
            }

            df.rename(columns=col_map, inplace=True)

            # ensure required
            for col in ["part_no","brand","price"]:
                if col not in df.columns:
                    df[col] = None

            df["part_no"] = df["part_no"].astype(str).apply(norm)
            df["brand"] = df["brand"].astype(str).str.strip()
            df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

            df = df[
                (df["part_no"] != "") &
                (df["brand"] != "")
            ]

            # 🔥 REMOVE NaN / INF
            df = df.replace([float("inf"), -float("inf")], 0)
            df = df.fillna(0)

            records = df.to_dict(orient="records")

            # 🔥 BATCH INSERT
            for i in range(0, len(records), 200):
                chunk = records[i:i+200]

                # 🔥 FIX INTEGER ISSUE
                for r in chunk:
                    r["price"] = safe_float(r.get("price"))

                supabase.table("parts_table").insert(chunk).execute()

            total += len(records)

        st.cache_data.clear()
        st.success(f"Uploaded {total} rows")
        st.rerun()

# ================= ADMIN =================
elif page == "🛠 Admin Panel":

    st.subheader("Add User")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Add User"):
        supabase.table("users").insert({
            "username": u,
            "password": p
        }).execute()
        st.success("User added")

    st.subheader("Remove User")

    users = supabase.table("users").select("username").execute().data
    user_list = [x["username"] for x in users if x["username"] != "admin"]

    if user_list:
        del_user = st.selectbox("Select user", user_list)

        if st.button("Delete User"):
            supabase.table("users").delete().eq("username", del_user).execute()
            st.success("User deleted")
