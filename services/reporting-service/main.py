import os
import psycopg2
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor

# --- Initialize FastAPI App ---
app = FastAPI()

# --- Database Connection Details (from environment variables) ---
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = "postgres"

# --- CORS Middleware ---
# Allows our frontend (running on localhost:3000) to communicate with this service.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_connection():
    """
    Establishes and returns a connection to the PostgreSQL database.
    Includes retry logic to handle initial startup race conditions.
    """
    conn = None
    for i in range(5):  # Retry 5 times
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
            )
            print("Reporting Service: Successfully connected to PostgreSQL.")
            return conn
        except psycopg2.OperationalError as e:
            print(
                f"Reporting Service: DB connection attempt {i+1} failed. Retrying in 2 seconds..."
            )
            time.sleep(2)

    # If connection fails after all retries
    print(f"ERROR: Could not connect to database after multiple attempts: {e}")
    raise HTTPException(status_code=503, detail="Database service is unavailable.")


@app.on_event("startup")
def startup_event():
    """
    On application startup, this function connects to the database and ensures
    the required 'test_results' table exists with the correct V2.0 schema.
    This makes the service self-sufficient.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create table with columns if it doesn't exist
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS test_results (
                id SERIAL PRIMARY KEY,
                test_case_id VARCHAR(255),
                objective TEXT,
                status VARCHAR(50),
                visual_status VARCHAR(50),
                step_results JSONB,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """
        )

        conn.commit()
        cursor.close()
        print("Reporting Service: Database table 'test_results' is ready.")
    except Exception as e:
        print(
            f"CRITICAL ERROR during startup: Could not initialize database table. {e}"
        )
    finally:
        if conn is not None:
            conn.close()


@app.get("/results")
def get_test_results():
    """
    Fetches the latest 100 test results from the database for the UI dashboard.
    """
    conn = None
    try:
        conn = get_db_connection()
        # RealDictCursor returns results as a list of dictionaries (JSON-friendly)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            "SELECT id, objective, status, visual_status, timestamp FROM test_results ORDER BY timestamp DESC LIMIT 100;"
        )
        results = cursor.fetchall()

        cursor.close()
        return results
    except Exception as e:
        print(f"ERROR fetching results: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch test results.")
    finally:
        if conn is not None:
            conn.close()


@app.get("/results/{run_id}")
def get_run_details(run_id: int):
    """
    Fetches all details for a single, specific test run by its primary key ID.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT * FROM test_results WHERE id = %s;", (run_id,))
        result = cursor.fetchone()

        cursor.close()

        if not result:
            raise HTTPException(
                status_code=404, detail=f"Test run with ID {run_id} not found."
            )

        return result
    except Exception as e:
        # Avoid re-raising the 404 we just threw
        if not isinstance(e, HTTPException):
            print(f"ERROR fetching result for ID {run_id}: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to fetch test run details."
            )
        raise e
    finally:
        if conn is not None:
            conn.close()


@app.get("/")
def read_root():
    """Root endpoint for health checks."""
    return {"message": "iQAP Reporting Service is running."}
