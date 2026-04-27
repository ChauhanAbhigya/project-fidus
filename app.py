from supabase import create_client
import streamlit as st
import pandas as pd
import os

# ---------------- SUPABASE ----------------
SUPABASE_URL = "https://eicwssbhjfvekaerjljm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVpY3dzc2JoamZ2ZWthZXJqbGptIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcyNzI1NTUsImV4cCI6MjA5Mjg0ODU1NX0.okPnbQrcKN6A2-Xj_99TgB47mtx9H6KO20asriBA19g".strip()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(layout="wide")

# ---------------- CACHE (FIXED) ----------------
@st.cache_data
def load_parts():
    try:
        data = supabase.table("parts_table").select("*").execute()
        return pd.DataFrame(data.data or [])
    except:
        return pd.DataFrame()

# ---------------- SESSION STATE ----------------
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

# ========================= PRICE PAGE =========================
if page == "📊 Price Lookup":

    # 🔄 REFRESH BUTTON (UNCHANGED)
    col_title, col_refresh = st.columns([10, 1])

    with col_refresh:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    db_df = load_parts()

    if db_df.empty:
        st.warning("⚠ No data found in database. Upload data first.")
        st.stop()

    db_df["brand_clean"] = db_df["brand"].astype(str).str.strip().str.lower()
    brand_list = sorted(db_df["brand_clean"].dropna().unique())

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

    def norm(x):
        if pd.isna(x):
            return ""
        x = str(x)
        x = x.replace(".0","")
        x = x.replace(" ","").replace("-","").replace("/","")
        x = x.lstrip("0")
        return x.strip().lower()

    if st.button("🔎 Fetch Prices"):

        result = []

        for _, row in input_df.iterrows():

            part = norm(row.get("Part No",""))
            brand = str(row.get("Brand","")).strip().lower()
            qty = pd.to_numeric(row.get("Qty"), errors="coerce")

            if not part:
                continue

            if pd.isna(qty) or qty == 0:
                qty = 1

            match = db_df[
                (db_df["part_no"] == part) &
                (db_df["brand_clean"] == brand)
            ]

            if not match.empty:
                r = match.iloc[0]
                price = float(r["price"])
                desc = r["description"]
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

    edited_df = st.session_state.table_data.copy()

    edited_df["Qty"] = pd.to_numeric(edited_df["Qty"], errors="coerce").fillna(0)
    edited_df["Price"] = pd.to_numeric(edited_df["Price"], errors="coerce").fillna(0)
    edited_df["Amount"] = edited_df["Qty"] * edited_df["Price"]

    st.dataframe(edited_df, use_container_width=True)

    st.markdown(f"### 💰 Total Amount: € {edited_df['Amount'].sum():.2f}")

    if st.button("💾 Save Offer"):
        for _, row in edited_df.iterrows():
            supabase.table("offer_items").insert({
                "username": username,
                "brand": row["Brand"],
                "part_no": row["Part No"],
                "qty": row["Qty"],
                "price": row["Price"],
                "amount": row["Amount"]
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

        total_rows = 0
        progress = st.progress(0)

        for i, uploaded_file in enumerate(uploaded_files):

            try:
                df = pd.read_excel(uploaded_file, dtype=str)

                df.columns = df.columns.str.lower().str.strip()

                df.rename(columns={
                    "part no": "part_no",
                    "price [eur]": "price",
                    "item description": "description"
                }, inplace=True)

                df["part_no"] = (
                    df["part_no"]
                    .astype(str)
                    .str.replace(".0","")
                    .str.replace(" ","")
                    .str.replace("-","")
                    .str.replace("/", "")
                    .str.lstrip("0")
                    .str.lower()
                )

                df["brand"] = df["brand"].astype(str).str.strip().str.lower()
                df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

                df = df[["brand","part_no","price","description"]]

                data = df.to_dict(orient="records")

                supabase.table("parts_table").insert(data).execute()

                total_rows += len(data)

            except Exception as e:
                st.error(f"❌ Error: {e}")

            progress.progress((i+1)/len(uploaded_files))

        st.success(f"Uploaded {total_rows} rows")

        # 🔥 FIXED REFRESH LOGIC
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
