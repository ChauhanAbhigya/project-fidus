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

def safe(v):
    try:
        if v is None or (isinstance(v,float) and (math.isnan(v) or math.isinf(v))):
            return 0
        return float(v)
    except:
        return 0

# ================= PRICE LOOKUP =================
if page == "📊 Price Lookup":

    # 🔥 FIX: ALWAYS FETCH BRANDS DIRECTLY FROM SUPABASE (NO CACHE)
    brand_data = supabase.table("parts_table").select("brand").execute()
    brand_df = pd.DataFrame(brand_data.data or [])

    if not brand_df.empty:
        brand_df["brand"] = brand_df["brand"].astype(str).str.strip()
        brand_df = brand_df[brand_df["brand"] != ""]
        brand_list = sorted(brand_df["brand"].unique().tolist())
    else:
        brand_list = []

    db_df = load_parts()

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
                (db_df["brand"].astype(str).str.strip().str.lower() == brand.lower())
            ]

            if not match.empty:
                row = match.iloc[0]
                price = safe(row.get("price"))
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

    edited_df = st.session_state.table_data.copy()

    for col in ["Qty","Price","Amount"]:
        if col not in edited_df.columns:
            edited_df[col] = 0

    edited_df["Qty"] = pd.to_numeric(edited_df["Qty"], errors="coerce").fillna(0)
    edited_df["Price"] = pd.to_numeric(edited_df["Price"], errors="coerce").fillna(0)
    edited_df["Amount"] = edited_df["Qty"] * edited_df["Price"]

    st.dataframe(edited_df, use_container_width=True)

    total = edited_df["Amount"].sum()
    st.markdown(f"### 💰 Total Amount: € {total:.2f}")

# ================= UPLOAD =================
elif page == "📤 Upload Data":

    uploaded = st.file_uploader("Upload Excel", type=["xlsx"], accept_multiple_files=True)

    if uploaded:
        total = 0

        for f in uploaded:

            df = pd.read_excel(f)
            df.columns = df.columns.str.strip().str.lower()

            df = df.rename(columns={
                "part no": "part_no",
                "price [eur]": "price",
                "item description": "description"
            })

            # 🔥 CLEAN BRAND ONLY (NO OTHER CHANGE)
            df["brand"] = df["brand"].astype(str).str.strip()
            df = df[df["brand"] != ""]

            df = df.fillna(0)

            data = df.to_dict(orient="records")

            supabase.table("parts_table").insert(data).execute()

            total += len(data)

        st.cache_data.clear()   # 🔥 ensures fresh load_parts
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
