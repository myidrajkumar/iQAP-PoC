import os
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor

app = FastAPI()

# --- DB Connection Details ---
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = "postgres"

# --- CORS ---
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def get_db_connection():
    """Establishes and returns a database connection."""
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)
        return conn
    except psycopg2.OperationalError as e:
        print(f"ERROR: Could not connect to database: {e}")
        raise HTTPException(status_code=503, detail="Database service unavailable.")

@app.on_event("startup")
def startup_event():
    """On startup, ensure the test_results table exists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id SERIAL PRIMARY KEY,
            test_case_id VARCHAR(255),
            objective TEXT,
            status VARCHAR(50),
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("Reporting Service: Database table 'test_results' is ready.")

@app.get("/results")
def get_test_results():
    """Fetches all test results from the database, newest first."""
    conn = get_db_connection()
    # RealDictCursor returns results as a list of dictionaries
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM test_results ORDER BY timestamp DESC LIMIT 100;")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

@app.get("/")
def read_root(): return {"message": "iQAP Reporting Service is running."}