import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import math
import re   # 🔥 added

# ---------------- DB ----------------
DATABASE_URL = "postgresql://parts_db_bi6b_user:vVxgefrTwrWGoHwzIPXbfemlrb4Fn6GW@dpg-d7o8oqgg4nts73aagbcg-a.oregon-postgres.render.com/parts_db_bi6b"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# ---------------- UI CONFIG ----------------
st.set_page_config(
    layout="wide",
    page_title="FIDUS Parts System",
    page_icon="⚙️"
)

# ---------------- PREMIUM UI (GLOBAL THEME) ----------------
st.markdown("""
<style>

/* Background gradient */
.stApp {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    color: white;
    font-family: 'Segoe UI', sans-serif;
}

/* Main container glass effect */
.block-container {
    padding: 2rem 2rem;
    background: rgba(255,255,255,0.05);
    border-radius: 20px;
    backdrop-filter: blur(10px);
}

/* Buttons */
div.stButton > button {
    background: linear-gradient(90deg, #00c6ff, #0072ff);
    color: white;
    border-radius: 10px;
    height: 42px;
    border: none;
    font-weight: 600;
    box-shadow: 0px 4px 15px rgba(0,0,0,0.3);
}

div.stButton > button:hover {
    transform: scale(1.02);
}

/* Dataframe */
.stDataFrame {
    background: rgba(255,255,255,0.08);
    border-radius: 12px;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #141e30, #243b55);
}

/* Inputs */
input, textarea {
    background-color: rgba(255,255,255,0.1) !important;
    color: white !important;
    border-radius: 8px !important;
}

</style>
""", unsafe_allow_html=True)

# ---------------- CREATE TABLE ----------------
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
INSERT INTO users (username, password)
SELECT 'admin','admin'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username='admin');
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
    st.session_state.table_data = pd.DataFrame(
        columns=["Brand","Part No","Description","Qty","Price","Amount"]
    )

if "input_table" not in st.session_state:
    st.session_state.input_table = pd.DataFrame(
        columns=["Brand","Part No","Qty"]
    )

if "user" not in st.session_state:
    st.session_state.user = None

# ---------------- LOGIN ----------------
def login(u,p):
    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s",(u,p))
    return cur.fetchone()

if st.session_state.user is None:

    st.markdown("<h1 style='text-align:center;color:#00c6ff;'>FIDUS Parts Portal</h1>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])

    with col2:
        st.image("logo.png", width=220)   # 🔥 LOGO LOGIN CENTER

        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Login"):
            if login(u,p):
                st.session_state.user = {"username":u}
                st.rerun()
            else:
                st.error("Invalid credentials")

    st.stop()

username = st.session_state.user["username"]

# ---------------- SIDEBAR ----------------
with st.sidebar:

    st.image("logo.png", width=160)   # 🔥 LOGO SIDEBAR

    st.markdown(f"### 👤 {username}")

    pages = ["📊 Price Lookup"]
    if username == "admin":
        pages += ["📤 Upload Data", "🛠 Admin Panel"]

    page = st.radio("Navigation", pages)

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# ---------------- HELPERS ----------------
def norm(x):
    if pd.isna(x):
        return ""
    x = str(x).lower().strip()
    x = re.sub(r'[^a-z0-9]', '', x)
    x = x.lstrip('0')
    return x

def safe_float(v):
    try:
        if pd.isna(v): return 0
        return float(v)
    except:
        return 0

def safe_int(v):
    try:
        return int(float(v))
    except:
        return 0

# ================= PRICE LOOKUP =================
if page == "📊 Price Lookup":

    st.title("📊 Price Lookup")

    db_df = load_parts()

    if db_df.empty:
        st.warning("No data found")
        st.stop()

    db_df["brand"] = db_df["brand"].astype(str).str.strip()
    brand_list = sorted(db_df["brand"].unique())

    db_df["part_norm"] = db_df["part_no"].apply(norm)
    db_df["brand_norm"] = db_df["brand"].apply(norm)

    col1, col2 = st.columns([10,1])
    with col2:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    input_df = st.data_editor(
        st.session_state.input_table,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Brand": st.column_config.SelectboxColumn("Brand", options=brand_list)
        }
    )

    if st.button("🔎 Fetch Prices"):

        result = []

        for _, r in input_df.iterrows():

            part = norm(r.get("Part No"))
            brand = norm(r.get("Brand"))

            qty = pd.to_numeric(r.get("Qty"), errors="coerce")
            if pd.isna(qty) or qty<=0:
                qty = 1

            match = db_df[
                (db_df["part_norm"] == part) &
                (db_df["brand_norm"] == brand)
            ]

            if not match.empty:
                row = match.iloc[0]
                price = safe_float(row["price"])
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

    df = st.session_state.table_data.copy()
    df["Amount"] = df["Qty"] * df["Price"]

    st.dataframe(df, use_container_width=True)
    st.success(f"Total: € {df['Amount'].sum():.2f}")

# ================= UPLOAD =================
elif page == "📤 Upload Data":

    st.title("📤 Upload Data")

    files = st.file_uploader("Upload Excel", type=["xlsx"], accept_multiple_files=True)

    if files:
        total = 0

        for f in files:

            df = pd.read_excel(f)
            df.columns = df.columns.str.strip().str.lower()

            df.rename(columns={
                "part no":"part_no",
                "price [eur]":"price",
                "item description":"description"
            }, inplace=True)

            df["part_no"] = df["part_no"].astype(str)
            df["brand"] = df["brand"].astype(str)
            df["price"] = pd.to_numeric(df["price"], errors="coerce")

            df = df.fillna(0)

            values = [
                (
                    r["part_no"],
                    r["brand"],
                    safe_float(r["price"]),
                    r.get("description"),
                    safe_int(r.get("moq"))
                )
                for _, r in df.iterrows()
            ]

            query = """
            INSERT INTO parts_table (part_no, brand, price, description, moq)
            VALUES %s
            """

            execute_values(cur, query, values)
            conn.commit()

            total += len(values)

        st.cache_data.clear()
        st.success(f"Uploaded {total} rows")

# ================= ADMIN =================
elif page == "🛠 Admin Panel":

    if username != "admin":
        st.error("Access Denied")
        st.stop()

    st.title("🛠 Admin Panel")

    st.subheader("Add User")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Add User"):
        cur.execute("INSERT INTO users (username,password) VALUES (%s,%s)",(u,p))
        conn.commit()
        st.success("User added")

    st.subheader("Remove User")

    cur.execute("SELECT username FROM users WHERE username!='admin'")
    users = [x[0] for x in cur.fetchall()]

    if users:
        d = st.selectbox("Select user", users)

        if st.button("Delete User"):
            cur.execute("DELETE FROM users WHERE username=%s",(d,))
            conn.commit()
            st.success("User removed")
