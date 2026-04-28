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
/* FULL BACKGROUND */
body {
    background: linear-gradient(135deg, #eef2ff, #fdf4ff);
}

/* MAIN CONTAINER */
.block-container {
    padding-top: 1rem;
    background: linear-gradient(135deg, #ffffff, #f8fafc);
    border-radius: 16px;
    padding: 20px;
}

/* SIDEBAR */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #6366f1, #8b5cf6);
}
section[data-testid="stSidebar"] * {
    color: white !important;
}

/* HEADER */
.main-title {
    font-size: 36px;
    font-weight: 700;
    margin-bottom: 10px;
}

/* LOGIN BOX */
.login-box {
    width: 420px;
    margin: auto;
    margin-top: 120px;
    padding: 40px;
    background: linear-gradient(135deg, #ffffff, #eef2ff);
    border-radius: 18px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.08);
    text-align: center;
}

/* BUTTON */
.stButton>button {
    background: linear-gradient(90deg, #6366f1, #3b82f6);
    color: white;
    border-radius: 10px;
    height: 42px;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)

# ---------------- LOAD DATA ----------------
@st.cache_data
def load_parts():
    data = supabase.table("parts_table").select("*").execute()
    return pd.DataFrame(data.data or [])

# 🔥 FIXED BRAND FETCH (NO CACHE ISSUE)
def load_brands():
    data = supabase.table("parts_table").select("brand").execute()
    df = pd.DataFrame(data.data or [])
    if df.empty:
        return []
    return sorted(
        df["brand"].astype(str).str.strip().str.lower().unique()
    )

# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None

if "table_data" not in st.session_state:
    st.session_state.table_data = pd.DataFrame(
        columns=["Brand","Part No","Description","Qty","Price","Amount"]
    )

if "input_table" not in st.session_state:
    st.session_state.input_table = pd.DataFrame(
        columns=["Brand","Part No","Qty"]
    )

# ---------------- LOGIN ----------------
def login(u, p):
    res = supabase.table("users")\
        .select("*")\
        .eq("username", u)\
        .eq("password", p)\
        .execute()
    return res.data[0] if res.data else None

if st.session_state.user is None:

    st.markdown("<div class='login-box'>", unsafe_allow_html=True)

    # ✅ CENTER LOGO
    if os.path.exists("logo.png"):
        st.image("logo.png", width=140)

    st.markdown("### 🔐 Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login", use_container_width=True):
        user = login(u, p)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Invalid credentials")

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
    return str(x).replace(".0","").replace(" ","").replace("-","").replace("/","").lower()

# ================= PRICE LOOKUP =================
if page == "📊 Price Lookup":

    if st.button("🔄 Refresh"):
        load_parts.clear()
        st.cache_data.clear()
        st.rerun()

    db_df = load_parts()

    db_df["part_no"] = db_df["part_no"].astype(str).apply(norm)
    db_df["brand"] = db_df["brand"].astype(str).str.lower().str.strip()

    # ✅ FIXED DROPDOWN
    brand_list = load_brands()

    input_df = st.data_editor(
        st.session_state.input_table,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Brand": st.column_config.SelectboxColumn(
                "Brand", options=brand_list
            )
        }
    )

    if st.button("🔎 Fetch Prices"):

        result = []

        for _, r in input_df.iterrows():

            part = norm(r.get("Part No"))
            brand = str(r.get("Brand","")).lower()

            match = db_df[
                (db_df["part_no"] == part) &
                (db_df["brand"] == brand)
            ]

            qty = pd.to_numeric(r.get("Qty"), errors="coerce")
            if pd.isna(qty) or qty <= 0:
                qty = 1

            if not match.empty:
                price = float(match.iloc[0]["price"])
                desc = match.iloc[0].get("description","")
            else:
                price = 0
                desc = "Not Found"

            result.append({
                "Brand": r["Brand"],
                "Part No": r["Part No"],
                "Description": desc,
                "Qty": qty,
                "Price": price,
                "Amount": qty * price
            })

        st.session_state.table_data = pd.DataFrame(result)

    df = st.session_state.table_data

    if not df.empty:
        st.dataframe(df, use_container_width=True)
        st.markdown(f"### 💰 Total: € {df['Amount'].sum():.2f}")

# ================= UPLOAD =================
elif page == "📤 Upload Data" and username == "admin":

    file = st.file_uploader("Upload Excel", type=["xlsx"])

    if file:
        df = pd.read_excel(file, dtype=str)
        df.columns = df.columns.str.strip().str.lower()

        df = df.rename(columns={
            "part no": "part_no",
            "brand": "brand",
            "price [eur]": "price",
            "item description": "description",
            "moq": "moq"
        })

        df["brand"] = df["brand"].str.lower().str.strip()
        df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

        data = df.to_dict(orient="records")

        # FIX NAN ERROR
        clean = []
        for r in data:
            row = {}
            for k,v in r.items():
                if pd.isna(v):
                    row[k] = None
                else:
                    row[k] = v
            clean.append(row)

        supabase.table("parts_table").insert(clean).execute()

        st.success("Uploaded successfully")
        st.rerun()

# ================= ADMIN =================
elif page == "🛠 Admin Panel" and username == "admin":

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
        selected = st.selectbox("Select User", user_list)

        if st.button("Delete User"):
            supabase.table("users").delete().eq("username", selected).execute()
            st.success("User deleted")
            st.rerun()
