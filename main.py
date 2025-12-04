from dotenv import load_dotenv
import os
import json
import re
import sqlite3
from sqlalchemy import create_engine, inspect

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq



load_dotenv()

# ------------------------ STEP 1: Extract Schema ------------------------

db_url = "sqlite:///amazon.db"

def extract_schema(db_url):
    engine = create_engine(db_url)
    inspector = inspect(engine)
    schema = {}

    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        schema[table_name] = [col["name"] for col in columns]

    return json.dumps(schema, indent=2)


# ------------------------ STEP 2: Text → SQL (with JOIN intelligence + repair mode) ------------------------

def text_to_sql(schema, prompt, error=None):
    if error:
        SYSTEM_PROMPT = f"""
        You are an expert SQL repair system.
        The previous SQL query FAILED with this error:

        ERROR:
        {error}

        FIX the SQL. Return ONLY valid raw SQL.
        DO NOT return markdown, backticks, or explanations.
        """
    else:
        SYSTEM_PROMPT = """
        You are an expert SQL generator.
        Your goals:
        - Output ONLY raw SQL.
        - NO markdown, NO ```sql blocks.
        - Use valid SQLite syntax.
        - Use JOINs intelligently.
        - Use ONLY tables/columns from the schema.
        """

    USER_PROMPT = """
    Schema:
    {schema}

    Question:
    {user_prompt}

    SQL Query:
    """

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", USER_PROMPT),
    ])

    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile",  
        temperature=0
    )

    chain = prompt_template | llm
    response = chain.invoke({"schema": schema, "user_prompt": prompt})

    raw = response.content if hasattr(response, "content") else response["content"]

    # Remove think tags
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)

    # Remove code fences & backticks
    cleaned = cleaned.replace("```sql", "")
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.replace("`", "")

    # Strip whitespace
    cleaned = cleaned.strip()

    return cleaned


# ------------------------ STEP 3: Execute SQL with Automatic Repair ------------------------

def run_sql_with_repair(sql_query, schema, prompt):
    conn = sqlite3.connect("amazon.db")
    cursor = conn.cursor()

    try:
        result = cursor.execute(sql_query)
        rows = result.fetchall()
        conn.close()
        return rows

    except Exception as e:
        conn.close()
        print("\n⛔ SQL Error — Attempting Auto-Repair...\n")
        print("Error:", e)

        repaired_sql = text_to_sql(schema, prompt, error=str(e))

        print("\n🔧 Repaired SQL Query:")
        print(repaired_sql)

        conn = sqlite3.connect("amazon.db")
        cursor = conn.cursor()

        try:
            result = cursor.execute(repaired_sql)
            rows = result.fetchall()
            conn.close()
            return rows
        except Exception as final_e:
            conn.close()
            return f"❌ SQL Repair Failed: {final_e}"


# ------------------------ STEP 4: Main Database Query Function ------------------------

def get_data_from_database(prompt):
    schema = extract_schema(db_url)
    sql_query = text_to_sql(schema, prompt)

    print("\nGenerated SQL Query:")
    print(sql_query)

    results = run_sql_with_repair(sql_query, schema, prompt)
    return results


# ------------------------ STEP 5: TEST RUN ------------------------

if __name__ == "__main__":
    test_prompt = "Show the top 5 most expensive products along with their category."

    print("📌 Question:", test_prompt)

    result = get_data_from_database(test_prompt)

    print("\n📊 Query Result:")
    print(result)

