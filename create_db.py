import pandas as pd
import sqlite3
import os

DB_NAME = "parts.db"
FOLDER = "data_files"

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS parts_table")

cursor.execute("""
CREATE TABLE parts_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT,
    part_no TEXT,
    price REAL,
    description TEXT,
    moq TEXT
)
""")

def clean_part(x):
    if pd.isna(x):
        return ""
    x = str(x)

    x = x.replace(".0","")
    x = x.strip()
    x = x.replace(" ","")
    x = x.replace("-","")
    x = x.replace("/","")

    x = x.lstrip("0")

    return x.lower()

for file in os.listdir(FOLDER):

    if file.endswith(".xlsx") and not file.startswith("~$"):

        path = os.path.join(FOLDER, file)

        try:
            df = pd.read_excel(path, dtype=str)

            df.columns = df.columns.str.lower().str.strip()

            df.rename(columns={
                "part no": "part_no",
                "brand": "brand",
                "price [eur]": "price",
                "item description": "description",
                "moq": "moq"
            }, inplace=True)

            if "part_no" not in df.columns or "price" not in df.columns:
                print("Skipping:", file)
                continue

            if "description" not in df.columns:
                df["description"] = "Not Available"

            if "moq" not in df.columns:
                df["moq"] = None

            df["part_no"] = df["part_no"].apply(clean_part)
            df["brand"] = df["brand"].astype(str).str.strip().str.lower()
            df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

            df = df[["brand","part_no","price","description","moq"]]
            df = df[df["part_no"] != ""]

            df.to_sql("parts_table", conn, if_exists="append", index=False)

            print("Loaded:", file)

        except Exception as e:
            print("Error:", file, e)
            cursor.execute("""
CREATE TABLE IF NOT EXISTS offer_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    brand TEXT,
    part_no TEXT,
    qty REAL,
    price REAL,
    amount REAL
)
""")

conn.commit()
conn.close()

print("✅ DB READY")