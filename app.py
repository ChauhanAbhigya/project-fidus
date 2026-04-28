from supabase import create_client
import streamlit as st
import pandas as pd
import os

# ---------------- SUPABASE ----------------
SUPABASE_URL = "https://eicwssbhjfvekaerjljm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVpY3dzc2JoamZ2ZWthZXJqbGptIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcyNzI1NTUsImV4cCI6MjA5Mjg0ODU1NX0.okPnbQrcKN6A2-Xj_99TgB47mtx9H6KO20asriBA19g"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(layout="wide")

# ---------------- CACHE ----------------
@st.cache_data(ttl=0)
def load_parts():
    try:
        data = supabase.table("parts_table").select("*").execute()
        return pd.DataFrame(data.data or [])
    except:
        return pd.DataFrame()

# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None

if "input_table" not in st.session_state:
    st.session_state.input_table = pd.DataFrame(columns=["Brand", "Part No", "Qty"])

if "table_data" not in st.session_state:
    st.session_state.table_data = pd.DataFrame()

# ---------------- LOGIN ----------------
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
            st.error("Invalid login")

    st.stop()

user = st.session_state.user
username = user["username"]

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.write(f"👤 {username}")

    pages = ["📊 Price Lookup"]
    if username == "admin":
        pages.append("📤 Upload Data")
        pages.append("🛠 Admin Panel")

    page = st.radio("Menu", pages)

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# ---------------- CLEAN FUNCTION ----------------
def clean(x):
    if pd.isna(x):
        return ""
    return str(x).strip().lower().replace(" ", "").replace("-", "").replace("/", "").lstrip("0")

# ---------------- UNIVERSAL EXCEL CLEANER ----------------
def clean_excel(df):
    df.columns = df.columns.str.strip().str.lower()

    mapping = {
        "part no": "part_no",
        "part number": "part_no",
        "brand": "brand",
        "price [eur]": "price_eur",
        "price": "price_eur",
        "item description": "item_description",
        "description": "item_description",
        "moq": "moq"
    }

    df.rename(columns=mapping, inplace=True)

    required = ["part_no", "brand", "price_eur"]
    for col in required:
        if col not in df.columns:
            df[col] = ""

    df["part_no"] = df["part_no"].apply(clean)
    df["brand"] = df["brand"].astype(str).str.lower().str.strip()

    df["price_eur"] = pd.to_numeric(df["price_eur"], errors="coerce").fillna(0)
    df["moq"] = pd.to_numeric(df.get("moq", 0), errors="coerce").fillna(0)

    df["item_description"] = df.get("item_description", "")

    df = df.dropna(subset=["part_no", "brand"])

    # FINAL SAFE CLEAN (IMPORTANT FIX)
    df = df.replace([float("inf"), -float("inf")], 0)
    df = df.fillna("")

    return df

# ================= PRICE LOOKUP =================
if page == "📊 Price Lookup":

    col1, col2 = st.columns([10, 1])
    with col2:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    db = load_parts()

    if db.empty:
        st.warning("No data found")
        st.stop()

    db["part_no"] = db["part_no"].astype(str).apply(clean)
    db["brand"] = db["brand"].astype(str).str.lower().str.strip()

    brand_list = sorted(db["brand"].unique())

    input_df = st.data_editor(
        st.session_state.input_table,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Brand": st.column_config.SelectboxColumn("Brand", options=brand_list)
        }
    )

    if st.button("Fetch Prices"):

        results = []

        for _, row in input_df.iterrows():

            part = clean(row.get("Part No"))
            brand = str(row.get("Brand", "")).strip().lower()
            qty = pd.to_numeric(row.get("Qty"), errors="coerce")
            if pd.isna(qty) or qty <= 0:
                qty = 1

            match = db[(db["part_no"] == part) & (db["brand"] == brand)]

            if not match.empty:
                r = match.iloc[0]
                price = float(r["price_eur"])
                desc = r.get("item_description", "")
            else:
                price = 0
                desc = "Not Found"

            results.append({
                "Brand": row.get("Brand"),
                "Part No": row.get("Part No"),
                "Description": desc,
                "Qty": qty,
                "Price": price,
                "Amount": qty * price
            })

        st.session_state.table_data = pd.DataFrame(results)
        st.success("Fetched")

    df = st.session_state.table_data.copy()

    if not df.empty:
        df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
        df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
        df["Amount"] = df["Qty"] * df["Price"]

        st.dataframe(df, use_container_width=True)
        st.write("Total:", df["Amount"].sum())

    if st.button("Save Offer") and not df.empty:

        for _, row in df.iterrows():

            supabase.table("offer_items").insert({
                "username": username,
                "brand": str(row["Brand"]),
                "part_no": str(row["Part No"]),
                "qty": float(row["Qty"]),
                "price": float(row["Price"]),
                "amount": float(row["Amount"])
            }).execute()

        st.success("Saved")

# ================= UPLOAD =================
elif page == "📤 Upload Data" and username == "admin":

    st.title("Upload Excel")

    files = st.file_uploader("Upload", type=["xlsx"], accept_multiple_files=True)

    if files:

        total = 0
        progress = st.progress(0)

        for i, f in enumerate(files):

            df = pd.read_excel(f)

            df = clean_excel(df)

            data = df.to_dict("records")

            # FINAL SAFETY FILTER (NO NAN CRASH)
            safe = []
            for r in data:
                clean_r = {}
                for k, v in r.items():
                    if pd.isna(v):
                        clean_r[k] = 0 if k in ["price_eur", "moq"] else ""
                    else:
                        clean_r[k] = v
                safe.append(clean_r)

            supabase.table("parts_table").insert(safe).execute()

            total += len(safe)
            progress.progress((i+1)/len(files))

        st.success(f"Uploaded {total}")

        st.cache_data.clear()
        st.rerun()

# ================= ADMIN =================
elif page == "🛠 Admin Panel" and username == "admin":

    st.subheader("Admin")

    u = st.text_input("New user")
    p = st.text_input("Password", type="password")

    if st.button("Add"):
        supabase.table("users").insert({
            "username": u,
            "password": p
        }).execute()
        st.success("Added")

    users = supabase.table("users").select("*").execute().data

    for x in users:
        st.write(x["username"])
