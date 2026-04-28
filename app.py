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

# ---------------- UI STYLE ONLY ----------------
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #0f172a, #1e293b, #0f172a);
    color: white;
    font-family: 'Segoe UI';
}

.main-title {
    font-size: 32px;
    font-weight: 700;
    background: linear-gradient(90deg, #00c6ff, #0072ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.stButton>button {
    background: linear-gradient(90deg, #00c6ff, #0072ff);
    color: white;
    border-radius: 10px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ---------------- CACHE ----------------
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
    res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
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

username = st.session_state.user["username"]

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
col1, col2 = st.columns([1,8])

with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=80)

with col2:
    st.markdown("<div class='main-title'>📊 Price Lookup System</div>", unsafe_allow_html=True)

# ---------------- NORMALIZER ----------------
def norm(x):
    if pd.isna(x):
        return ""
    return str(x).replace(".0","").replace(" ","").replace("-","").replace("/","").lstrip("0").strip().lower()

# ================= PRICE PAGE =================
if page == "📊 Price Lookup":

    col1, col2 = st.columns([9,1])

    with col2:
        if st.button("🔄"):
            st.cache_data.clear()
            st.rerun()

    db_df = load_parts()

    if db_df.empty:
        st.warning("No data found")
        st.stop()

    db_df["part_no"] = db_df["part_no"].astype(str).apply(norm)
    db_df["brand"] = db_df["brand"].astype(str).str.lower()

    input_df = st.data_editor(st.session_state.input_table, num_rows="dynamic")

    if st.button("🔎 Fetch Prices"):
        result = []

        for _, r in input_df.iterrows():
            part = norm(r["Part No"])
            brand = str(r["Brand"]).lower()
            qty = float(r["Qty"] or 1)

            match = db_df[(db_df["part_no"] == part) & (db_df["brand"] == brand)]

            if not match.empty:
                row = match.iloc[0]
                price = float(row["price"])
                desc = row.get("description", "")
            else:
                price = 0
                desc = "Not found"

            result.append({
                "Brand": r["Brand"],
                "Part No": r["Part No"],
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

    # ---------------- SAVE OFFER ----------------
    if st.button("💾 Save Offer"):

        batch = []

        for _, row in df.iterrows():

            batch.append({
                "username": username,
                "brand": str(row["Brand"]),
                "part_no": str(row["Part No"]),
                "qty": float(row["Qty"] or 0),
                "price": float(row["Price"] or 0),
                "amount": float(row["Amount"] or 0)
            })

        # 🚀 FAST BULK INSERT (FIX SPEED ISSUE)
        BATCH_SIZE = 100

        for i in range(0, len(batch), BATCH_SIZE):
            supabase.table("offer_items").insert(batch[i:i+BATCH_SIZE]).execute()

        st.success("Saved successfully")

# ================= UPLOAD PAGE (FAST VERSION) =================
elif page == "📤 Upload Data" and username == "admin":

    st.title("📤 Upload Excel")

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

            df = df[["part_no","brand","price","description","moq"]]

            df["part_no"] = df["part_no"].astype(str).apply(norm)
            df["brand"] = df["brand"].astype(str).str.lower()

            df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

            df = df.replace([float("inf"), -float("inf")], 0)
            df = df.fillna("")

            records = df.to_dict("records")

            # 🚀 BULK INSERT SPEED FIX
            for j in range(0, len(records), 200):
                supabase.table("parts_table").insert(records[j:j+200]).execute()

            total += len(records)
            progress.progress((i+1)/len(files))

        st.success(f"Uploaded {total} rows")
        st.cache_data.clear()
        st.rerun()

# ================= ADMIN =================
elif page == "🛠 Admin Panel" and username == "admin":

    st.subheader("Admin Panel")

    u = st.text_input("New user")
    p = st.text_input("Password")

    if st.button("Add"):
        supabase.table("users").insert({"username": u, "password": p}).execute()
        st.success("Added")
