# 🔥 CLEAN DATA
df = df.drop_duplicates(subset=["brand","part_no"])

# 🔥 CONVERT TO LIST
data = df.to_dict(orient="records")

# 🔥 CHUNK UPLOAD
BATCH_SIZE = 500

progress = st.progress(0)

for i in range(0, len(data), BATCH_SIZE):
    batch = data[i:i+BATCH_SIZE]

    supabase.table("parts_table").insert(batch).execute()

    progress.progress(min((i + BATCH_SIZE) / len(data), 1.0))

st.success(f"✅ Uploaded {len(data)} rows successfully!")