import streamlit as st
import pandas as pd
import sqlite3
import os
from main import extract_schema, text_to_sql

# ---------- Page Config ----------
st.set_page_config(
    page_title="SQLGenie ✨",
    page_icon="🧞‍♂️",
    layout="wide"
)

# ------------------------ STATE INIT ------------------------
if "db_path" not in st.session_state:
    st.session_state.db_path = "amazon.db"   # default DB

if "latest_sql" not in st.session_state:
    st.session_state.latest_sql = None
if "latest_result" not in st.session_state:
    st.session_state.latest_result = None
if "latest_columns" not in st.session_state:
    st.session_state.latest_columns = None


# ---------- Import Raw SQL Executor ----------
def execute_sql_raw(sql_query):
    """Executes SQL on the current active database."""
    conn = sqlite3.connect(st.session_state.db_path)
    cur = conn.cursor()
    try:
        rows = cur.execute(sql_query).fetchall()
        col_names = [desc[0] for desc in cur.description] if cur.description else []
        conn.close()
        return rows, col_names
    except Exception as e:
        conn.close()
        return f"❌ SQL Error: {e}", None


# ---------- CSV → SQLite Converter ----------
def convert_csv_to_sqlite(csv_file, sqlite_path):
    df = pd.read_csv(csv_file)
    table_name = os.path.splitext(os.path.basename(csv_file.name))[0]

    conn = sqlite3.connect(sqlite_path)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()

    return table_name


# ---------- Custom CSS ----------
st.markdown(
    """
    <style>
        .main > div { display: flex; justify-content: center; }
        .app-card {
            max-width: 1000px; width: 100%;
            padding: 2.5rem 3rem; border-radius: 1.5rem;
            background: radial-gradient(circle at top left, #1b1b33, #0a0a20);
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 24px 60px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.05);
        }
        .app-title {
            font-size: 2.6rem; font-weight: 800; margin-bottom: .25rem;
            background: linear-gradient(90deg, #c084fc, #06b6d4, #8b5cf6);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
    </style>
    """, unsafe_allow_html=True
)


# ======================= UI START =======================
with st.container():
    st.markdown('<div class="app-card">', unsafe_allow_html=True)

    col_main, col_side = st.columns([3, 1.4])

    with col_main:
        st.markdown('<div class="app-title">🧞‍♂️ SQLGenie</div>', unsafe_allow_html=True)
        st.markdown(
            "Ask anything about your data. SQLGenie will generate & execute SQL "
            "to give you instant insights."
        )

    with col_side:
        st.markdown("### 📁 Upload Your Dataset")
        uploaded = st.file_uploader("Upload .csv or .db", type=["csv", "db"])

        if uploaded:
            if uploaded.name.endswith(".db"):
                # Save DB
                new_db_path = "uploaded_database.db"
                with open(new_db_path, "wb") as f:
                    f.write(uploaded.getbuffer())
                st.session_state.db_path = new_db_path
                st.success("Database uploaded successfully!")

            elif uploaded.name.endswith(".csv"):
                new_db_path = "uploaded_database.db"
                table = convert_csv_to_sqlite(uploaded, new_db_path)
                st.session_state.db_path = new_db_path
                st.success(f"CSV uploaded and converted! Table created: `{table}`")

        st.markdown("### 💡 Ask:")
        st.markdown("""
        • Top 5 expensive products  
        • Customers who purchased electronics  
        • Revenue by month  
        """)

    st.markdown("---")

    # ---------- Input Form ----------
    with st.form("query-form"):
        user_query = st.text_area(
            "💬 What do you want to know?",
            placeholder="e.g., Show customers who purchased electronics",
            height=110,
        )
        submitted = st.form_submit_button("✨ Ask SQLGenie", use_container_width=True)


    # ---------- Process Query ----------
    if submitted and user_query.strip():

        with st.spinner("🧞‍♂️ SQLGenie is working..."):
            schema_json = extract_schema(f"sqlite:///{st.session_state.db_path}")
            generated_sql = text_to_sql(schema_json, user_query)
            result = execute_sql_raw(generated_sql)

        if isinstance(result, tuple):
            rows, cols = result
        else:
            rows, cols = None, None

        st.session_state.latest_sql = generated_sql
        st.session_state.latest_result = rows
        st.session_state.latest_columns = cols


    # ================= DISPLAY SQL & RESULTS =================
    if st.session_state.latest_sql:
        st.subheader("🧾 Generated SQL")
        st.code(st.session_state.latest_sql, language="sql")

        # Allow modification
        edited_sql = st.text_area("✏️ Modify SQL", st.session_state.latest_sql, height=150)

        if st.button("⚡ Run Modified SQL", use_container_width=True):
            result = execute_sql_raw(edited_sql)
            if isinstance(result, tuple):
                st.session_state.latest_sql = edited_sql
                st.session_state.latest_result = result[0]
                st.session_state.latest_columns = result[1]
            else:
                st.error(result)

    # Show Results
    if st.session_state.latest_result is not None:
        st.subheader("📊 Query Results")

        rows = st.session_state.latest_result
        cols = st.session_state.latest_columns

        if isinstance(rows, str):
            st.error(rows)
        else:
            if rows and cols:
                df = pd.DataFrame(rows, columns=cols)
                st.dataframe(df, use_container_width=True)

                # ---------- CSV Download ----------
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download results as CSV",
                    data=csv,
                    file_name="sqlgenie_results.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            else:
                st.info("No rows returned.")

    st.markdown("</div>", unsafe_allow_html=True)
