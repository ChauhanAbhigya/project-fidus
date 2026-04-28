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

# ---------------- PREMIUM UI (FIXED) ----------------
st.markdown("""
<style>

/* FULL PAGE GRADIENT FIX */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #f5f7ff, #eef2ff);
}

/* SIDEBAR */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #667eea, #764ba2);
}
section[data-testid="stSidebar"] * {
    color: white !important;
}

/* CARD UI */
.block {
    background: white;
    padding: 18px;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
}

/* BUTTON */
.stButton>button {
    background: linear-gradient(90deg, #667eea, #5a67d8);
    color: white;
    border-radius: 8px;
    height: 40px;
    border: none;
}

/* TITLE FIX */
.main-title {
    font-size: 30px;
    font-weight: 700;
    color: #1a237e;
}

/* LOGIN CENTER FIX */
.login-box {
    max-width: 400px;
    margin: auto;
    margin-top: 80px;
    padding: 30px;
    border-radius: 14px;
    background: white;
    box-shadow: 0 8px 30px rgba(0,0,0,0.08);
    text-align: center;
}

</style>
""", unsafe_allow_html=True)

# ---------------- CACHE ----------------
@st.cache_data
def load_parts():
    data = supabase.table("parts_table").select("*").execute()
    df = pd.DataFrame(data.data or [])
    if not df.empty:
        df["brand"] = df["brand"].astype(str).str.strip().str.lower()
    return df

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

# ---------------- LOGIN UI ----------------
if st.session_state.user is None:

    st.markdown("<div class='login-box'>", unsafe_allow_html=True)

    # CENTER LOGO
    if os.path.exists("logo.png"):
        st.image("logo.png", width=150)

    st.markdown("### 🔐 Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login(u, p)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Invalid username or password")

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ---------------- USER ----------------
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

def safe(v):
    try:
        if v is None or (isinstance(v,float) and (math.isnan(v) or math.isinf(v))):
            return 0
        return float(v)
    except:
        return 0

# ========================= PRICE PAGE =========================
if page == "📊 Price Lookup":

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    db_df = load_parts()

    # ✅ BRAND FIX (REAL FIX)
    brand_list = sorted(db_df["brand"].dropna().unique().tolist())

    input_df = st.data_editor(
        pd.DataFrame(columns=["Brand","Part No","Qty"]),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Brand": st.column_config.SelectboxColumn(
                "Brand",
                options=brand_list
            )
        }
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
                (db_df["part_no"].astype(str).apply(norm) == part) &
                (db_df["brand"] == brand)
            ]

            if not match.empty:
                row = match.iloc[0]
                price = safe(row.get("price"))
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

    if "table_data" in st.session_state:
        df = st.session_state.table_data

        st.dataframe(df, use_container_width=True)

        st.markdown(f"### 💰 Total: € {df['Amount'].sum():.2f}")

# ========================= UPLOAD =========================
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

            df["brand"] = df["brand"].astype(str).str.lower()

            # ✅ FINAL FIX FOR NAN ERROR
            df = df.fillna(0)

            data = df.to_dict(orient="records")

            supabase.table("parts_table").insert(data).execute()

            total += len(data)

        st.success(f"Uploaded {total} rows")

# ========================= ADMIN =========================
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
