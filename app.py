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

# ---------------- CACHE (FAST BRAND LOAD) ----------------
@st.cache_data
def load_brands():
    cur.execute("SELECT DISTINCT brand FROM parts_table ORDER BY brand")
    return [x[0] for x in cur.fetchall()]

# ---------------- SESSION ----------------
if "table_data" not in st.session_state:
    st.session_state.table_data = pd.DataFrame(columns=[
        "Brand","Part No","Description","Qty","Price","Amount"
    ])

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
        st.image("logo.png", width=160)
        st.markdown("### 👤 Sign In")

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
    st.image("logo.png", width=140)
    st.markdown(f"### 👤 {username}")

    if username == "admin":
        pages = ["📊 Price Lookup","📁 Saved Quotations","📤 Data Upload","🛠 Access Control"]
    else:
        pages = ["📊 Price Lookup","📁 Saved Quotations"]

    page = st.radio("WorkSpace", pages)

    st.markdown("---")

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# ================= PRICE LOOKUP =================
if page == "📊 Price Lookup":
    set_bg("#f0f7ff","#e6f0ff")

    col1, col2 = st.columns([10,1])
    with col1:
        st.title("Price Lookup Panel")
    with col2:
        if st.button("🔄"):
            st.cache_data.clear()
            st.rerun()

    # ✅ FAST brand load
    brand_list = load_brands()

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

            part = str(r.get("Part No","")).strip()
            brand = str(r.get("Brand","")).strip()

            qty = pd.to_numeric(r.get("Qty"), errors="coerce")
            if pd.isna(qty) or qty <= 0:
                qty = 1

            price = 0
            desc = "Not Found"

            if part and brand:
                cur.execute("""
                    SELECT price, description
                    FROM parts_table
                    WHERE LOWER(part_no)=LOWER(%s)
                    AND LOWER(brand)=LOWER(%s)
                    LIMIT 1
                """, (part, brand))

                match = cur.fetchone()

                if match:
                    price, desc = match

            result.append({
                "Brand": brand,
                "Part No": part,
                "Description": desc,
                "Qty": qty,
                "Price": float(price),
                "Amount": qty * float(price)
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
        df = pd.DataFrame(json.loads(data) if isinstance(data,str) else data)
        df["Employee"] = user
        df["Saved On"] = date
        df["Offer ID"] = offer_id
        all_data.append(df)

    final_df = pd.concat(all_data, ignore_index=True)

    employees = ["All"] + sorted(final_df["Employee"].unique())
    selected_emp = st.selectbox("Filter by Employee", employees)

    if selected_emp != "All":
        final_df = final_df[final_df["Employee"] == selected_emp]

    final_df["Description"] = final_df["Description"].astype(str).str.slice(0, 40)
    final_df.insert(0, "Select", False)

    edited_df = st.data_editor(final_df, use_container_width=True, height=350)

    output = BytesIO()
    final_df.to_excel(output, index=False)
    output.seek(0)

    st.download_button("⬇ Download Excel", output, file_name="saved_offers.xlsx")

    st.markdown("---")
    if st.button("Delete Selected Quotations"):
        selected = edited_df[edited_df["Select"] == True]

        if not selected.empty:
            ids = selected["Offer ID"].unique().tolist()
            cur.execute("DELETE FROM saved_offers WHERE id = ANY(%s)", (ids,))
            conn.commit()
            st.success("Deleted successfully")
            st.rerun()

# ================= UPLOAD =================
elif page == "📤 Data Upload":
    set_bg("#f5f0ff","#ede9fe")
    st.title("Master Data Upload")

    files = st.file_uploader("Upload Price Sheet", type=["xlsx"], accept_multiple_files=True)

    if files:
        for f in files:
            df = pd.read_excel(f)
            df.columns = df.columns.str.strip().str.lower()

            df.rename(columns={
                "part no": "part_no",
                "price [eur]": "price",
                "item description": "description",
                "moq": "moq"
            }, inplace=True)

            df["moq"] = pd.to_numeric(df.get("moq", 0), errors="coerce").fillna(0)

            values = [
                (r["part_no"], r["brand"], float(r["price"]), r.get("description",""), int(r["moq"]))
                for _, r in df.iterrows()
            ]

            execute_values(
                cur,
                "INSERT INTO parts_table (part_no,brand,price,description,moq) VALUES %s",
                values
            )
            conn.commit()

        st.cache_data.clear()
        st.success("Uploaded successfully")
        st.rerun()

# ================= ADMIN =================
# ================= ADMIN =================
elif page == "🛠 Access Control":
    set_bg("#f3f6ff", "#e8edff")
    st.title("User & Access Control")

    # ---------------- CREATE USER ----------------
    st.subheader("➕ Create User Account")

    u = st.text_input("New Username", key="create_user_name")
    p = st.text_input("New Password", type="password", key="create_user_pass")

    if st.button("Create User", key="create_user_btn"):
        if u and p:
            try:
                cur.execute(
                    "INSERT INTO users (username,password) VALUES (%s,%s)",
                    (u, p)
                )
                conn.commit()
                st.success("User Created Successfully")
            except:
                st.error("User already exists")
        else:
            st.warning("Enter username and password")

    st.markdown("---")

    # ---------------- REMOVE USER ----------------
    st.subheader("🗑 Remove User")

    cur.execute("SELECT username FROM users WHERE username != 'admin'")
    users = [x[0] for x in cur.fetchall()]

    del_user = st.selectbox(
        "Select User",
        ["-- Select --"] + users,
        key="delete_user_select"
    )

    if st.button("Delete User", key="delete_user_btn"):
        if del_user != "-- Select --":
            cur.execute("DELETE FROM users WHERE username=%s", (del_user,))
            conn.commit()
            st.success(f"User '{del_user}' deleted")
        else:
            st.warning("Select a user first")

    st.markdown("---")

    # ---------------- CHANGE ADMIN PASSWORD ----------------
    st.subheader("🔐 Change Admin Password")

    current = st.text_input("Current Password", type="password", key="admin_current_pass")
    new_pass = st.text_input("New Password", type="password", key="admin_new_pass")

    if st.button("Update Password", key="admin_update_btn"):
        cur.execute("SELECT password FROM users WHERE username='admin'")
        real = cur.fetchone()

        if real and current == real[0]:
            cur.execute(
                "UPDATE users SET password=%s WHERE username='admin'",
                (new_pass,)
            )
            conn.commit()
            st.success("Password updated")
        else:
            st.error("Wrong current password")
