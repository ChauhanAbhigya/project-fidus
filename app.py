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
    data = supabase.table("parts_table").select("*").execute()
    return pd.DataFrame(data.data or [])

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
    res = supabase.table("users").select("*")\
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

# ---------------- SAFE NORMALIZER ----------------
def norm(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return str(x).replace(".0","").replace(" ","").replace("-","").replace("/","").lstrip("0").strip().lower()

# ---------------- SAFE SUPABASE CLEAN (FIX) ----------------
def safe_value(v):
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
    if pd.isna(v):
        return None
    return v

def clean_for_supabase(df):
    df = df.copy()

    df = df.replace([float("inf"), -float("inf")], None)
    df = df.where(pd.notnull(df), None)

    records = []
    for _, row in df.iterrows():
        clean_row = {}
        for k, v in row.items():
            clean_row[k] = safe_value(v)
        records.append(clean_row)

    return records

# ========================= PRICE PAGE =========================
if page == "📊 Price Lookup":

    col_title, col_refresh = st.columns([10, 1])

    with col_refresh:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    db_df = load_parts()

    if db_df.empty:
        st.warning("⚠ No data found in database. Upload data first.")
        st.stop()

    db_df["part_no"] = db_df["part_no"].astype(str).apply(norm)
    db_df["brand"] = db_df["brand"].astype(str).str.strip().str.lower()

    brand_list = sorted(db_df["brand"].dropna().unique())

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

        for _, row in input_df.iterrows():

            part = norm(row.get("Part No",""))
            brand = str(row.get("Brand","")).strip().lower()
            qty = pd.to_numeric(row.get("Qty"), errors="coerce")

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
        st.success("Prices fetched successfully")

    df = st.session_state.table_data.copy()

    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
    df["Amount"] = df["Qty"] * df["Price"]

    st.dataframe(df, use_container_width=True)
    st.markdown(f"### 💰 Total: € {df['Amount'].sum():.2f}")

    if st.button("💾 Save Offer"):

        safe_rows = []

        for _, row in df.iterrows():
            safe_rows.append({
                "username": username,
                "brand": str(row["Brand"]),
                "part_no": str(row["Part No"]),
                "qty": float(row["Qty"] or 0),
                "price": float(row["Price"] or 0),
                "amount": float(row["Amount"] or 0)
            })

        BATCH = 50
        for i in range(0, len(safe_rows), BATCH):
            supabase.table("offer_items").insert(safe_rows[i:i+BATCH]).execute()

        st.success("Saved successfully")

# ========================= UPLOAD PAGE (FIXED ONLY ERROR) =========================
elif page == "📤 Upload Data" and username == "admin":

    st.title("📤 Upload Excel Data")

    uploaded_files = st.file_uploader(
        "Upload Excel Files",
        type=["xlsx"],
        accept_multiple_files=True
    )

    if uploaded_files:

        total_rows = 0
        progress = st.progress(0)

        for i, uploaded_file in enumerate(uploaded_files):

            try:
                df = pd.read_excel(uploaded_file, dtype=str)

                df.columns = df.columns.str.strip().str.lower()

                df.rename(columns={
                    "part no": "part_no",
                    "price [eur]": "price",
                    "item description": "description",
                    "moq": "moq"
                }, inplace=True)

                df = df[["part_no", "brand", "price", "description", "moq"]]

                df["part_no"] = df["part_no"].apply(norm)
                df["brand"] = df["brand"].astype(str).str.lower().str.strip()

                df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
                df["moq"] = pd.to_numeric(df["moq"], errors="coerce").fillna(1)

                df = df.dropna(subset=["part_no", "brand"])

                # FINAL FIX (IMPORTANT)
                records = clean_for_supabase(df)

                if len(records) > 0:
                    BATCH = 100
                    for j in range(0, len(records), BATCH):
                        supabase.table("parts_table").insert(records[j:j+BATCH]).execute()

                total_rows += len(records)

            except Exception as e:
                st.error(f"❌ Error: {e}")

            progress.progress((i+1)/len(uploaded_files))

        st.success(f"Uploaded {total_rows} rows")
        st.cache_data.clear()
        st.rerun()

# ========================= ADMIN PANEL =========================
elif page == "🛠 Admin Panel" and username == "admin":

    st.subheader("Admin Panel")

    new_user = st.text_input("New Username")
    new_pass = st.text_input("Password", type="password")

    if st.button("Add User"):
        supabase.table("users").insert({
            "username": new_user,
            "password": new_pass
        }).execute()
        st.success("User added")

    users = supabase.table("users").select("username").execute().data
    user_list = [u["username"] for u in users if u["username"] != "admin"]

    if user_list:
        selected_user = st.selectbox("Select User", user_list)

        if st.button("Delete User"):
            supabase.table("users").delete().eq("username", selected_user).execute()
            st.success("User deleted")
