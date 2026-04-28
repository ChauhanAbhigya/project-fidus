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

# ---------------- SAFE CLEANERS ----------------
def safe_str(x):
    if pd.isna(x):
        return ""
    return str(x).strip()

def safe_float(x):
    try:
        if pd.isna(x):
            return 0.0
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return 0.0
        return v
    except:
        return 0.0

def safe_int(x):
    try:
        if pd.isna(x):
            return 0
        return int(float(x))
    except:
        return 0

def norm(x):
    if pd.isna(x):
        return ""
    return str(x).replace(".0","").replace(" ","").replace("-","").replace("/","").lstrip("0").strip().lower()

# ---------------- LOAD DATA ----------------
@st.cache_data(ttl=0)
def load_parts():
    data = supabase.table("parts_table").select("*").execute()
    return pd.DataFrame(data.data or [])

# ---------------- SESSION ----------------
if "table_data" not in st.session_state:
    st.session_state.table_data = pd.DataFrame(columns=["Brand","Part No","Description","Qty","Price","Amount"])

if "input_table" not in st.session_state:
    st.session_state.input_table = pd.DataFrame(columns=["Brand","Part No","Qty"])

# ---------------- LOGIN ----------------
if "user" not in st.session_state:
    st.session_state.user = None

def login(u, p):
    res = supabase.table("users").select("*").eq("username", u.strip()).eq("password", p.strip()).execute()
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
            st.error("Invalid login")

    st.stop()

user = st.session_state.user
username = user["username"]

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown(f"👤 {username}")

    pages = ["📊 Price Lookup"]
    if username == "admin":
        pages += ["📤 Upload Data", "🛠 Admin Panel"]

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
    st.title("📊 Price Lookup System")

# ================= PRICE LOOKUP =================
if page == "📊 Price Lookup":

    db_df = load_parts()

    if db_df.empty:
        st.warning("No data")
        st.stop()

    db_df["part_no"] = db_df["part_no"].astype(str).apply(norm)
    db_df["brand"] = db_df["brand"].astype(str).str.lower()

    input_df = st.data_editor(st.session_state.input_table, num_rows="dynamic", key="editor")

    if st.button("Fetch Prices"):

        result = []

        for _, row in input_df.iterrows():

            part = norm(row.get("Part No",""))
            brand = str(row.get("Brand","")).lower()
            qty = safe_float(row.get("Qty"))

            if not part:
                continue

            if qty <= 0:
                qty = 1

            match = db_df[(db_df["part_no"] == part) & (db_df["brand"] == brand)]

            if not match.empty:
                r = match.iloc[0]
                price = safe_float(r.get("price"))
                desc = safe_str(r.get("description"))
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

    df = st.session_state.table_data.copy()

    df["Qty"] = df["Qty"].apply(safe_float)
    df["Price"] = df["Price"].apply(safe_float)
    df["Amount"] = df["Qty"] * df["Price"]

    st.dataframe(df)

    st.write("Total:", df["Amount"].sum())

    if st.button("Save Offer"):

        safe_rows = []

        for _, r in df.iterrows():
            safe_rows.append({
                "username": username,
                "brand": safe_str(r["Brand"]),
                "part_no": safe_str(r["Part No"]),
                "qty": safe_float(r["Qty"]),
                "price": safe_float(r["Price"]),
                "amount": safe_float(r["Amount"])
            })

        # FIX: batch insert (prevents timeout)
        for i in range(0, len(safe_rows), 50):
            supabase.table("offer_items").insert(safe_rows[i:i+50]).execute()

        st.success("Saved")

# ================= UPLOAD =================
elif page == "📤 Upload Data" and username == "admin":

    uploaded = st.file_uploader("Upload Excel", type=["xlsx"], accept_multiple_files=True)

    if uploaded:

        all_data = []

        for file in uploaded:

            df = pd.read_excel(file)

            df.columns = df.columns.str.strip().str.lower()

            # UNIVERSAL mapping
            df = df.rename(columns={
                "part no": "part_no",
                "price [eur]": "price",
                "item description": "description",
                "moq": "moq"
            })

            for col in ["part_no", "brand", "price"]:
                if col not in df.columns:
                    df[col] = ""

            if "description" not in df.columns:
                df["description"] = ""

            if "moq" not in df.columns:
                df["moq"] = 0

            df["part_no"] = df["part_no"].apply(norm)
            df["brand"] = df["brand"].astype(str).str.lower()
            df["price"] = df["price"].apply(safe_float)
            df["moq"] = df["moq"].apply(safe_int)

            df = df.fillna("")

            records = df.to_dict("records")
            all_data.extend(records)

        # FIX: batch insert (avoid timeout)
        for i in range(0, len(all_data), 50):
            supabase.table("parts_table").insert(all_data[i:i+50]).execute()

        st.success(f"Uploaded {len(all_data)} rows")

# ================= ADMIN =================
elif page == "🛠 Admin Panel" and username == "admin":

    u = st.text_input("New User")
    p = st.text_input("Pass", type="password")

    if st.button("Add"):
        supabase.table("users").insert({"username": u, "password": p}).execute()
        st.success("Added")
