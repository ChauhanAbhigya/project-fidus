import streamlit as st
import pandas as pd
from db import get_connection, init_db
import os

port = int(os.environ.get("PORT", 10000))

st.set_page_config(layout="wide")

init_db()
conn = get_connection()

# ---------------- CACHE ----------------
@st.cache_data
def load_parts():
    return pd.read_sql("SELECT * FROM parts_table", conn)

# ---------------- SESSION STATE ----------------
if "table_data" not in st.session_state:
    st.session_state.table_data = pd.DataFrame(
        columns=["Brand","Part No","Description","Qty","Price","Amount"]
    )

if "input_table" not in st.session_state:
    st.session_state.input_table = pd.DataFrame(
        columns=["Brand","Part No","Qty"]
    )

# ---------------- UI ----------------
st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: 'Segoe UI', sans-serif;
}
.block-container {
    background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
    padding: 2rem;
    border-radius: 14px;
    border: 1px solid rgba(0,0,0,0.05);
}
.stButton>button {
    background: linear-gradient(90deg, #2563eb, #3b82f6);
    color: white;
    border-radius: 8px;
    height: 38px;
}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e3a8a, #2563eb);
}
section[data-testid="stSidebar"] * {
    color: white !important;
}
.main-title {
    font-size: 26px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ---------------- LOGIN ----------------
if "user" not in st.session_state:
    st.session_state.user = None

def login(u, p):
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (u.strip(), p.strip())
    ).fetchone()
    return user

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
            st.error("Invalid username or password. Please try again.")

    st.stop()

user = st.session_state.user
username = user[1]

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown(f"👤 Logged in as: **{username}**")

    pages = ["📊 Price Lookup",]
    if username == "admin":
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
    st.markdown("<div class='main-title'>📊Price Lookup System</div>", unsafe_allow_html=True)

# ========================= PRICE PAGE =========================
if page == "📊 Price Lookup":

    brand_df = pd.read_sql("SELECT DISTINCT brand FROM parts_table", conn)
    brand_list = sorted(brand_df["brand"].dropna().tolist())

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
        x = x.replace(" ","")
        x = x.replace("-","")
        x = x.replace("/","")
        x = x.lstrip("0")
        return x.strip().lower()

    if st.button("🔎 Fetch Prices"):

        db_df = load_parts()
        db_df["brand_clean"] = db_df["brand"].astype(str).str.strip().str.lower()

        result = []

        for _, row in input_df.iterrows():

            part = norm(row.get("Part No",""))
            brand = str(row.get("Brand","")).strip().lower()
            qty = pd.to_numeric(row.get("Qty"), errors="coerce")

            if not part:
                st.warning("Part number cannot be empty")
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
                desc = "Item not found in database"

            amount = qty * price

            result.append({
                "Brand": row.get("Brand"),
                "Part No": row.get("Part No"),
                "Description": desc,
                "Qty": qty,
                "Price": price,
                "Amount": amount
            })

        st.session_state.table_data = pd.DataFrame(result)

        st.session_state.input_table = pd.DataFrame(
            columns=["Brand","Part No","Qty"]
        )

        st.success("Prices fetched successfully")

    edited_df = st.session_state.table_data.copy()

    for col in ["Qty","Price","Amount"]:
        if col not in edited_df.columns:
            edited_df[col] = 0

    edited_df = edited_df.copy()

    edited_df["Qty"] = pd.to_numeric(edited_df["Qty"], errors="coerce").fillna(0)
    edited_df["Price"] = pd.to_numeric(edited_df["Price"], errors="coerce").fillna(0)
    edited_df["Amount"] = edited_df["Qty"] * edited_df["Price"]

    edited_df = edited_df.reset_index(drop=True)
    edited_df.index = edited_df.index + 1

    def highlight_rows(row):
        if row["Price"] == 0:
            return ["background-color: #ffe6e6"] * len(row)
        return [""] * len(row)

    st.dataframe(
        edited_df.style.apply(highlight_rows, axis=1),
        use_container_width=True
    )

    total = edited_df["Amount"].sum()
    st.markdown(f"### 💰 Total Amount: € {total:.2f}")

    if st.button("💾 Save Offer"):

        if edited_df.empty:
            st.warning("No data to save")
        else:
            if edited_df.duplicated(["Brand","Part No"]).any():
                st.warning("⚠ Duplicate items found. Please review before saving.")

            for _, row in edited_df.iterrows():
                conn.execute(
                    "INSERT INTO offer_items (username, brand, part_no, qty, price, amount) VALUES (?,?,?,?,?,?)",
                    (
                        username,
                        row["Brand"],
                        row["Part No"],
                        row["Qty"],
                        row["Price"],
                        row["Amount"]
                    )
                )

            # 🔥 ACTIVITY LOG
            conn.execute(
                "INSERT INTO logs (username, action) VALUES (?,?)",
                (username, "Saved Offer")
            )

            conn.commit()
            st.success("Saved successfully")

# ========================= SAVED OFFERS =========================


# ========================= ADMIN =========================
elif page == "🛠 Admin Panel" and username == "admin":

    st.subheader("Admin Panel")

    # ---------------- ADD USER ----------------
    st.markdown("### ➕ Add User")

    new_user = st.text_input("New Username")
    new_pass = st.text_input("Password", type="password")

    if st.button("Add User"):
        try:
            conn.execute(
                "INSERT INTO users (username,password) VALUES (?,?)",
                (new_user, new_pass)
            )
            conn.commit()
            st.success("User added")
        except:
            st.error("User already exists")

    # ---------------- REMOVE USER ----------------
    st.markdown("### ❌ Remove User")

    users_df = pd.read_sql("SELECT username FROM users", conn)

    user_list = [u for u in users_df["username"].tolist() if u != "admin"]

    if len(user_list) == 0:
        st.info("No users available to delete")
    else:
        selected_user = st.selectbox("Select User to Delete", user_list)

        if st.button("Delete User"):
            conn.execute(
                "DELETE FROM users WHERE username=?",
                (selected_user,)
            )
            conn.commit()
            st.success(f"User '{selected_user}' deleted")

    # ---------------- CHANGE ADMIN PASSWORD ----------------
    st.markdown("### 🔐 Change Admin Password")

    current_pass = st.text_input("Current Password", type="password")
    new_pass_admin = st.text_input("New Password", type="password")
    confirm_pass = st.text_input("Confirm New Password", type="password")

    if st.button("Update Password"):

        # verify current password
        check = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            ("admin", current_pass)
        ).fetchone()

        if not check:
            st.error("Current password is incorrect")
        elif new_pass_admin != confirm_pass:
            st.error("New passwords do not match")
        elif new_pass_admin.strip() == "":
            st.error("New password cannot be empty")
        else:
            conn.execute(
                "UPDATE users SET password=? WHERE username=?",
                (new_pass_admin, "admin")
            )
            conn.commit()
            st.success("Password updated successfully")