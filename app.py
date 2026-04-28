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

# ---------------- CACHE ----------------
@st.cache_data(ttl=0)
def load_parts():
    data = supabase.table("parts_table").select("*").execute()
    return pd.DataFrame(data.data or [])

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
    res = supabase.table("users").select("*")\
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

username = st.session_state.user["username"]

# ---------------- NORMALIZER ----------------
def norm(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return str(x).replace(".0","").replace(" ","").replace("-","").replace("/","").lstrip("0").lower().strip()

# ---------------- CLEAN EXCEL ----------------
def clean_excel(df):
    df.columns = df.columns.str.strip().str.lower()

    # universal mapping for YOUR file
    df = df.rename(columns={
        "part no": "part_no",
        "part number": "part_no",
        "brand": "brand",
        "price [eur]": "price",
        "item description": "description",
        "moq": "moq"
    })

    # ensure columns exist
    for col in ["part_no","brand","price","description","moq"]:
        if col not in df.columns:
            df[col] = None

    # clean part no
    df["part_no"] = df["part_no"].apply(norm)
    df["brand"] = df["brand"].astype(str).str.lower().str.strip()

    # FIX PRICE + MOQ TYPES (IMPORTANT)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df["moq"] = pd.to_numeric(df["moq"], errors="coerce").fillna(1).astype(int)

    df["description"] = df["description"].fillna("N/A")

    df = df.dropna(subset=["part_no","brand"])

    # remove bad JSON values
    df = df.replace([float("inf"), -float("inf")], 0)

    return df

# ---------------- PRICE PAGE ----------------
if True:

    db_df = load_parts()

    if not db_df.empty:
        db_df["part_no"] = db_df["part_no"].apply(norm)
        db_df["brand"] = db_df["brand"].str.lower().str.strip()

    if st.button("🔎 Fetch Prices"):

        result = []

        for _, row in st.session_state.input_table.iterrows():

            part = norm(row.get("Part No"))
            brand = str(row.get("Brand","")).lower().strip()
            qty = pd.to_numeric(row.get("Qty"), errors="coerce")

            if qty is None or math.isnan(qty) or qty <= 0:
                qty = 1

            match = db_df[
                (db_df["part_no"] == part) &
                (db_df["brand"] == brand)
            ]

            if not match.empty:
                r = match.iloc[0]
                price = float(r["price"])
                desc = r["description"]
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

    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
    df["Amount"] = df["Qty"] * df["Price"]

    st.dataframe(df, use_container_width=True)
    st.markdown(f"### 💰 Total: € {df['Amount'].sum():.2f}")

    # ---------------- SAVE (FIXED BATCH + NO NAN CRASH) ----------------
    if st.button("💾 Save Offer"):

        clean_rows = []

        for _, r in df.iterrows():
            clean_rows.append({
                "username": username,
                "brand": str(r["Brand"]),
                "part_no": str(r["Part No"]),
                "qty": int(float(r["Qty"] or 0)),
                "price": float(r["Price"] or 0),
                "amount": float(r["Amount"] or 0)
            })

        # BATCH INSERT (fix timeout)
        BATCH = 50
        for i in range(0, len(clean_rows), BATCH):
            supabase.table("offer_items").insert(clean_rows[i:i+BATCH]).execute()

        st.success("Saved successfully")

# ---------------- UPLOAD (SAFE + BATCH) ----------------
if username == "admin" and st.button("Upload Excel"):

    uploaded = st.file_uploader("Upload Excel", type=["xlsx"], accept_multiple_files=True)

    if uploaded:

        all_rows = []

        for file in uploaded:

            df = pd.read_excel(file)
            df = clean_excel(df)

            all_rows.extend(df.to_dict("records"))

        # FIX: batch insert (prevents timeout)
        BATCH = 100

        for i in range(0, len(all_rows), BATCH):
            chunk = all_rows[i:i+BATCH]
            supabase.table("parts_table").insert(chunk).execute()

        st.success("Upload complete")
        st.cache_data.clear()
