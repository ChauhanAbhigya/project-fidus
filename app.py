import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import re
import json
from io import BytesIO

# ---------------- DB ----------------
DATABASE_URL = "postgresql://parts_db_bi6b_user:vVxgefrTwrWGoHwzIPXbfemlrb4Fn6GW@dpg-d7o8oqgg4nts73aagbcg-a.oregon-postgres.render.com/parts_db_bi6b"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

st.set_page_config(layout="wide")

st.markdown("""
<style>
section[data-testid="stSidebar"] {
    width: 280px !important;
}
section[data-testid="stSidebar"] > div {
    width: 280px !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------- BG ----------------
def set_bg(c1, c2):
    st.markdown(f"""
    <style>
    .stApp {{
        background: linear-gradient(135deg, {c1} 0%, {c2} 100%);
        background-attachment: fixed;
    }}
    </style>
    """, unsafe_allow_html=True)

# ---------------- TABLES ----------------
cur.execute("""
CREATE TABLE IF NOT EXISTS parts_table (
    id SERIAL PRIMARY KEY,
    part_no TEXT,
    brand TEXT,
    price NUMERIC,
    description TEXT,
    moq INTEGER
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS saved_offers (
    id SERIAL PRIMARY KEY,
    username TEXT,
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
""")

cur.execute("""
INSERT INTO users (username,password)
SELECT 'admin','admin'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username='admin')
""")

conn.commit()

# ---------------- CACHE ----------------
@st.cache_data
def load_parts():
    df = pd.read_sql("SELECT * FROM parts_table", conn)
    df.columns = df.columns.str.lower()
    return df

# ---------------- SESSION ----------------
if "table_data" not in st.session_state:
    st.session_state.table_data = pd.DataFrame(columns=["Brand","Part No","Description","Qty","Price","Amount"])

if "input_table" not in st.session_state:
    st.session_state.input_table = pd.DataFrame(columns=["Brand","Part No","Qty"])

if "user" not in st.session_state:
    st.session_state.user = None

# ---------------- LOGIN ----------------
def login(u,p):
    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s",(u,p))
    return cur.fetchone()

if st.session_state.user is None:

    st.markdown("<style>section[data-testid='stSidebar']{display:none;}</style>", unsafe_allow_html=True)
    set_bg("#eef4ff","#f8fbff")

    col1,col2,col3 = st.columns([1,2,1])
    with col2:
        st.image("logo.png", width=170)
        st.markdown("### 👤Sign In")

        u = st.text_input("Enter Username")
        p = st.text_input("Enter Password", type="password")

        if st.button("Click me to Continue"):
            if login(u,p):
                st.session_state.user = {"username":u}
                st.rerun()
            else:
                st.error("Invalid credentials")

    st.stop()

username = st.session_state.user["username"]

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.image("logo.png", width=150)
    st.markdown(f"### 👤 {username}")

    if username == "admin":
        pages = ["📊 Price Lookup ","📁 Saved Quotations","📤 Data Upload","🛠Access Control"]
    else:
        pages = ["📊 Price Lookup ","📁 Saved Quotations"]

    page = st.radio("WorkSpace", pages)

    st.markdown("---")

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# ---------------- HELPERS ----------------
def norm(x):
    if pd.isna(x): return ""
    return re.sub(r'[^a-z0-9]', '', str(x).lower()).lstrip('0')

def safe_float(v):
    try: return float(v)
    except: return 0

# ================= PRICE LOOKUP =================
if page == "📊 Price Lookup ":
    set_bg("#f0f7ff","#e6f0ff")
    st.title("Price Lookup Panel")

    db_df = load_parts()

    db_df["brand"] = db_df["brand"].astype(str).str.strip()
    brand_list = sorted(db_df["brand"].unique())

    db_df["part_norm"] = db_df["part_no"].apply(norm)
    db_df["brand_norm"] = db_df["brand"].apply(norm)

    input_df = st.data_editor(
        st.session_state.input_table,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Brand": st.column_config.SelectboxColumn("Brand", options=brand_list)
        }
    )

    if st.button("Get Pricing"):
        result = []
        for _, r in input_df.iterrows():
            match = db_df[
                (db_df["part_norm"] == norm(r["Part No"])) &
                (db_df["brand_norm"] == norm(r["Brand"]))
            ]

            price = match.iloc[0]["price"] if not match.empty else 0
            desc = match.iloc[0]["description"] if not match.empty else "Not Found"
            qty = int(r["Qty"]) if pd.notna(r["Qty"]) else 1

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
    st.dataframe(df, use_container_width=True)

    if st.button("💾 Save Quotation"):
        if not df.empty:
            cur.execute(
                "INSERT INTO saved_offers (username,data) VALUES (%s,%s)",
                (username, json.dumps(df.to_dict(orient="records")))
            )
            conn.commit()
            st.success("Quotation saved successfully")

# ================= SAVED QUOTATIONS =================
elif page == "📁 Saved Quotations":
    set_bg("#f0fff4","#e6fffa")
    st.title("Saved Quotations")

    cur.execute("SELECT id, username, data, created_at FROM saved_offers ORDER BY created_at DESC")
    rows = cur.fetchall()

    if not rows:
        st.info("No saved offers")
        st.stop()

    all_data = []

    for offer_id, user, data, date in rows:
        if isinstance(data, str):
            df = pd.DataFrame(json.loads(data))
        else:
            df = pd.DataFrame(data)

        df["Employee"] = user
        df["Saved On"] = date
        df["Offer ID"] = offer_id

        all_data.append(df)

    final_df = pd.concat(all_data, ignore_index=True)

    # Filter
    employees = ["All"] + sorted(final_df["Employee"].unique())
    selected_emp = st.selectbox("Filter by Employee", employees)

    if selected_emp != "All":
        final_df = final_df[final_df["Employee"] == selected_emp]

    # Trim description (no scroll)
    final_df["Description"] = final_df["Description"].astype(str).str.slice(0, 40)

    # Checkbox first column
    final_df.insert(0, "Select", False)

    edited_df = st.data_editor(
        final_df,
        use_container_width=True,
        height=350,
        column_config={
            "Select": st.column_config.CheckboxColumn("✔", width="small"),
            "Brand": st.column_config.Column(width="small"),
            "Part No": st.column_config.Column(width="small"),
            "Description": st.column_config.Column(width="medium"),
            "Qty": st.column_config.Column(width="small"),
            "Price": st.column_config.Column(width="small"),
            "Amount": st.column_config.Column(width="small"),
            "Employee": st.column_config.Column(width="small"),
            "Saved On": st.column_config.Column(width="small"),
        }
    )

    # Download
    output = BytesIO()
    final_df.to_excel(output, index=False)
    output.seek(0)

    st.download_button("⬇ Download Excel", output, file_name="saved_offers.xlsx")

    # Delete
    st.markdown("---")
    st.subheader("🗑 Delete Selected Quotations")

    if st.button("Delete Selected Quotations"):

        selected_rows = edited_df[edited_df["Select"] == True]

        if selected_rows.empty:
            st.warning("No rows selected")

        else:
            ids_to_delete = selected_rows["Offer ID"].unique().tolist()

            cur.execute(
                "DELETE FROM saved_offers WHERE id = ANY(%s)",
                (ids_to_delete,)
            )
            conn.commit()

            st.success(f"{len(ids_to_delete)} quotation(s) deleted")
            st.rerun()

# ================= UPLOAD =================
elif page == "📤 Data Upload":
    set_bg("#f5f0ff","#ede9fe")
    st.title("Master Data Upload")

    files = st.file_uploader("Upload Price Sheet", type=["xlsx"], accept_multiple_files=True)

    if files:
        for f in files:
            df = pd.read_excel(f)

            # 🔥 Normalize columns
            df.columns = df.columns.str.strip().str.lower()

            # 🔥 Exact rename based on your format
            df.rename(columns={
                "part no": "part_no",
                "price [eur]": "price",
                "item description": "description",
                "moq": "moq"
            }, inplace=True)

            # 🔥 Validate
            required = ["part_no", "brand", "price"]
            missing = [c for c in required if c not in df.columns]

            if missing:
                st.error(f"Missing columns: {missing}")
                st.stop()

            # 🔥 Clean data
            df["part_no"] = df["part_no"].astype(str)
            df["brand"] = df["brand"].astype(str)
            df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

            if "description" not in df.columns:
                df["description"] = ""

            if "moq" not in df.columns:
                df["moq"] = 0

            # 🔥 Insert
            values = [
                (
                    r["part_no"],
                    r["brand"],
                    float(r["price"]),
                    r["description"],
                    int(r["moq"]) if pd.notna(r["moq"]) else 0
                )
                for _, r in df.iterrows()
            ]

            execute_values(
                cur,
                "INSERT INTO parts_table (part_no,brand,price,description,moq) VALUES %s",
                values
            )
            conn.commit()

        st.success("Uploaded successfully")

# ================= ADMIN =================
elif page == "🛠Access Control":
    set_bg("#f3f6ff","#e8edff")
    st.title("User & Access Control")

    st.subheader("➕ Create User Account")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Create User"):
        cur.execute("INSERT INTO users (username,password) VALUES (%s,%s)",(u,p))
        conn.commit()
        st.success("User Created")

    st.subheader("🔐Update Admin Credentials")
    current = st.text_input("Current Password", type="password")
    new_pass = st.text_input("New Password", type="password")

    if st.button("Update Password"):
        cur.execute("SELECT password FROM users WHERE username='admin'")
        real_pass = cur.fetchone()[0]

        if current == real_pass:
            cur.execute("UPDATE users SET password=%s WHERE username='admin'", (new_pass,))
            conn.commit()
            st.success("Password updated")
        else:
            st.error("Wrong current password")
