import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import math

# ---------------- DB CONNECTION ----------------
DATABASE_URL = "postgresql://parts_db_bi6b_user:vVxgefrTwrWGoHwzIPXbfemlrb4Fn6GW@dpg-d7o8oqgg4nts73aagbcg-a.oregon-postgres.render.com/parts_db_bi6b"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# ---------------- CREATE TABLES ----------------
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

# default admin
cur.execute("""
INSERT INTO users (username, password)
SELECT 'admin', 'admin'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username='admin');
""")

conn.commit()

st.set_page_config(layout="wide")

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

# ---------------- LOGIN ----------------
if "user" not in st.session_state:
    st.session_state.user = None

def login(u, p):
    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (u, p))
    return cur.fetchone()

if st.session_state.user is None:
    st.title("🔐 Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login(u.strip(), p.strip())
        if user:
            st.session_state.user = {"username": u}
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

username = st.session_state.user["username"]

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

def safe_float(v):
    try:
        if v is None or (isinstance(v,float) and (math.isnan(v) or math.isinf(v))):
            return 0.0
        return float(v)
    except:
        return 0.0

def safe_int(v):
    try:
        return int(float(v))
    except:
        return 0

# ================= PRICE LOOKUP =================
if page == "📊 Price Lookup":

    db_df = load_parts()

    if db_df.empty:
        st.warning("No data found")
        st.stop()

    db_df["brand"] = db_df["brand"].astype(str).str.strip()
    db_df = db_df[db_df["brand"] != ""]

    brand_list = sorted(db_df["brand"].unique().tolist())

    # 🔄 refresh
    col1, col2 = st.columns([10,1])
    with col2:
        if st.button("🔄"):
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
            brand = str(r.get("Brand","")).strip()

            qty = pd.to_numeric(r.get("Qty"), errors="coerce")
            if pd.isna(qty) or qty <= 0:
                qty = 1

            match = db_df[
                (db_df["part_no"].astype(str).apply(norm) == part) &
                (db_df["brand"].str.lower() == brand.lower())
            ]

            if not match.empty:
                row = match.iloc[0]
                price = safe_float(row.get("price"))
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

    df = st.session_state.table_data.copy()
    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
    df["Amount"] = df["Qty"] * df["Price"]

    st.dataframe(df, use_container_width=True)
    st.markdown(f"### 💰 Total: € {df['Amount'].sum():.2f}")

# ================= UPLOAD (FAST ⚡) =================
elif page == "📤 Upload Data":

    uploaded = st.file_uploader("Upload Excel", type=["xlsx"], accept_multiple_files=True)

    if uploaded:
        total = 0
        progress = st.progress(0)

        for i, f in enumerate(uploaded):

            df = pd.read_excel(f)
            df.columns = df.columns.str.strip().str.lower()

            col_map = {
                "part no": "part_no",
                "part number": "part_no",
                "price [eur]": "price",
                "item description": "description"
            }

            df.rename(columns=col_map, inplace=True)

            for col in ["part_no","brand","price"]:
                if col not in df.columns:
                    df[col] = None

            df["part_no"] = df["part_no"].astype(str).apply(norm)
            df["brand"] = df["brand"].astype(str).str.strip()
            df["price"] = pd.to_numeric(df["price"], errors="coerce")

            df = df[(df["part_no"] != "") & (df["brand"] != "")]

            df = df.replace([float("inf"), -float("inf")], 0)
            df = df.fillna(0)

            records = df.to_dict(orient="records")

            # ⚡ FAST BULK INSERT
            values = [
                (
                    r.get("part_no"),
                    r.get("brand"),
                    safe_float(r.get("price")),
                    r.get("description"),
                    safe_int(r.get("moq"))
                )
                for r in records
            ]

            query = """
            INSERT INTO parts_table (part_no, brand, price, description, moq)
            VALUES %s
            """

            execute_values(cur, query, values)
            conn.commit()

            total += len(records)
            progress.progress((i+1)/len(uploaded))

        st.cache_data.clear()
        st.success(f"Uploaded {total} rows")
        st.rerun()

# ================= ADMIN =================
elif page == "🛠 Admin Panel":

    st.subheader("Add User")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Add User"):
        cur.execute("INSERT INTO users (username, password) VALUES (%s,%s)", (u,p))
        conn.commit()
        st.success("User added")

    st.subheader("Remove User")

    cur.execute("SELECT username FROM users WHERE username!='admin'")
    users = [x[0] for x in cur.fetchall()]

    if users:
        del_user = st.selectbox("Select user", users)

        if st.button("Delete User"):
            cur.execute("DELETE FROM users WHERE username=%s", (del_user,))
            conn.commit()
            st.success("User deleted")
