import streamlit as st
import pandas as pd
import sqlite3

# ---------------- DB ----------------
conn = sqlite3.connect("parts.db", check_same_thread=False)

# ---------------- AUTH CHECK ----------------
if "user" not in st.session_state:
    st.warning("Please login first")
    st.stop()

st.title("📂 Saved Offers")

# ---------------- FETCH DATA ----------------
df = pd.read_sql("SELECT * FROM offer_items ORDER BY id DESC", conn)

# ---------------- NO DATA ----------------
if df.empty:
    st.info("No saved data found")
    st.stop()

# ---------------- FILTER ----------------
st.markdown("### 🔍 Filter by Employee")

employees = ["All"] + sorted(df["username"].dropna().unique().tolist())
selected = st.selectbox("Select Employee", employees)

if selected != "All":
    df = df[df["username"] == selected]

# ---------------- FORMAT ----------------
df_display = df.rename(columns={
    "username": "Employee",
    "brand": "Brand",
    "part_no": "Part No",
    "qty": "Qty",
    "price": "Price",
    "amount": "Amount"
})

# ---------------- SERIAL NUMBER ----------------
df_display = df_display.reset_index(drop=True)
df_display.index = df_display.index + 1

# ---------------- DISPLAY ----------------
st.dataframe(df_display, use_container_width=True)

# ---------------- TOTAL ----------------
total = df_display["Amount"].sum()
st.markdown(f"### 💰 Total Amount: € {total:.2f}")

# ---------------- DOWNLOAD EXCEL ----------------
def convert_to_excel(df):
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

excel_data = convert_to_excel(df_display)

st.download_button(
    label="📥 Download Excel",
    data=excel_data,
    file_name="saved_offers.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)