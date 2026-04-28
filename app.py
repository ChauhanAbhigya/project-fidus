from supabase import create_client
import streamlit as st
import pandas as pd
import os
import math

# ---------------- SUPABASE ----------------
SUPABASE_URL = "https://eicwssbhjfvekaerjljm.supabase.co"
SUPABASE_KEY = "YOUR_KEY_HERE"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Price System", layout="wide")

# ---------------- PREMIUM LIGHT UI ----------------
st.markdown("""
<style>
body {
    background: linear-gradient(135deg, #f6f9ff, #eef3ff);
}

.main-title {
    font-size: 32px;
    font-weight: 700;
    color: #1a237e;
}

.card {
    background: white;
    padding: 15px;
    border-radius: 12px;
    box-shadow: 0px 4px 20px rgba(0,0,0,0.05);
}
</style>
""", unsafe_allow_html=True)

# ---------------- LOAD DATA ----------------
@st.cache_data(ttl=0)
def load_parts():
    try:
        res = supabase.table("parts_table").select("*").execute()
        return pd.DataFrame(res.data or [])
    except:
        return pd.DataFrame()

# ---------------- SESSION ----------------
if "table_data" not in st.session_state:
    st.session_state.table_data = pd.DataFrame()

if "input_table" not in st.session_state:
    st.session_state.input_table = pd.DataFrame(columns=["Brand", "Part No", "Qty"])

# ---------------- NORMALIZER ----------------
def norm(x):
    if pd.isna(x):
        return ""
    return str(x).replace(".0", "").replace(" ", "").replace("-", "").replace("/", "").strip().lower()

# ---------------- SAFE VALUE ----------------
def safe(v, is_int=False):
    try:
        if v is None:
            return None
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        if is_int:
            return int(float(v))
        return float(v)
    except:
        return v

# ---------------- CLEAN EXCEL ----------------
def clean_excel(df):

    df.columns = df.columns.str.strip().str.lower()

    mapping = {
        "part no": "part_no",
        "part number": "part_no",
        "brand": "brand",
        "price [eur]": "price",
        "price": "price",
        "item description": "description",
        "description": "description",
        "moq": "moq"
    }

    df = df.rename(columns=mapping)

    for col in ["part_no", "brand", "price"]:
        if col not in df.columns:
            df[col] = None

    if "description" not in df.columns:
        df["description"] = None

    if "moq" not in df.columns:
        df["moq"] = 0

    df["part_no"] = df["part_no"].astype(str).apply(norm)
    df["brand"] = df["brand"].astype(str).str.lower()

    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df["moq"] = pd.to_numeric(df["moq"], errors="coerce").fillna(0)

    df = df.dropna(subset=["part_no", "brand"])

    df = df.replace([float("inf"), -float("inf")], None)
    df = df.where(pd.notnull(df), None)

    return df

# ---------------- UI HEADER ----------------
st.markdown("<div class='main-title'>📊 Price Lookup System</div>", unsafe_allow_html=True)

# ---------------- LOAD DB ----------------
db_df = load_parts()

if db_df.empty:
    st.warning("Upload data first")
    st.stop()

db_df["part_no"] = db_df["part_no"].astype(str).apply(norm)
db_df["brand"] = db_df["brand"].astype(str).str.lower()

# ---------------- INPUT ----------------
st.subheader("Enter Parts")

input_df = st.data_editor(
    st.session_state.input_table,
    num_rows="dynamic",
    use_container_width=True
)

# ---------------- FETCH PRICES ----------------
if st.button("🔎 Fetch Prices"):

    result = []

    for _, r in input_df.iterrows():

        part = norm(r.get("Part No"))
        brand = str(r.get("Brand","")).lower()
        qty = pd.to_numeric(r.get("Qty"), errors="coerce")

        if pd.isna(qty) or qty <= 0:
            qty = 1

        match = db_df[
            (db_df["part_no"] == part) &
            (db_df["brand"] == brand)
        ]

        if not match.empty:
            row = match.iloc[0]
            price = float(row.get("price", 0))
            desc = row.get("description", "N/A")
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

# ---------------- RESULT TABLE ----------------
df = st.session_state.table_data

if not df.empty:

    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
    df["Amount"] = df["Qty"] * df["Price"]

    st.dataframe(df, use_container_width=True)

    st.markdown(f"### 💰 Total: € {df['Amount'].sum():.2f}")

# ---------------- SAVE OFFER ----------------
if st.button("💾 Save Offer") and not df.empty:

    records = []

    for _, r in df.iterrows():
        records.append({
            "username": "user",
            "brand": r["Brand"],
            "part_no": r["Part No"],
            "qty": safe(r["Qty"], True),
            "price": safe(r["Price"]),
            "amount": safe(r["Amount"])
        })

    # BULK SAFE INSERT
    for i in range(0, len(records), 200):
        supabase.table("offer_items").insert(records[i:i+200]).execute()

    st.success("Saved successfully")

# ---------------- UPLOAD ----------------
st.subheader("Upload Excel")

files = st.file_uploader("Upload", type=["xlsx"], accept_multiple_files=True)

if files:

    total = 0

    for f in files:

        df = pd.read_excel(f, dtype=str)
        df = clean_excel(df)

        data = df.to_dict(orient="records")

        # safe insert
        for i in range(0, len(data), 200):
            supabase.table("parts_table").insert(data[i:i+200]).execute()

        total += len(data)

    st.success(f"Uploaded {total} rows")
    st.cache_data.clear()
