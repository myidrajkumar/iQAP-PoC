import os
import time
import psycopg2
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor

# --- Database Connection Details (from environment variables) ---
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = "postgres"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    The modern, recommended way to manage application startup and shutdown.
    This will run on startup before the application starts receiving requests.
    """
    print("Reporting Service: Lifespan startup event...")

    conn = None
    # This resilient loop ensures the service doesn't fully start until the DB is ready.
    while True:
        try:
            print("Reporting Service: Attempting to connect to PostgreSQL...")
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
            )
            print("Reporting Service: Successfully connected to PostgreSQL.")
            cursor = conn.cursor()

            # Create table with schema if it doesn't exist
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
            break  # Exit the loop on success

        except psycopg2.OperationalError:
            print(
                "Reporting Service: PostgreSQL not ready yet. Waiting 5 seconds to retry..."
            )
            # Use asyncio.sleep for non-blocking waits in an async context
            await asyncio.sleep(5)
        except Exception as e:
            print(
                f"CRITICAL ERROR during startup: Could not initialize database table. {e}"
            )
            await asyncio.sleep(5)  # Wait before retrying on other errors
        finally:
            if conn is not None:
                conn.close()

    # --- The application is now running ---
    yield
    # --- Shutdown logic would go here, after the yield ---
    print("Reporting Service: Lifespan shutdown event...")


# --- Initialize FastAPI App with the new lifespan manager ---
app = FastAPI(lifespan=lifespan)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_connection():
    """Establishes and returns a database connection for API calls."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"ERROR: Could not connect to database during API call: {e}")
        raise HTTPException(status_code=503, detail="Database service is unavailable.")


@app.get("/results")
def get_test_results():
    """Fetches the latest 100 test results from the database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id, objective, status, visual_status, timestamp FROM test_results ORDER BY timestamp DESC LIMIT 100;"
        )
        results = cursor.fetchall()
        cursor.close()
        return results
    except Exception as e:
        print(f"ERROR fetching results: {e}")
        # This will catch the "relation does not exist" error if the table somehow wasn't created
        raise HTTPException(
            status_code=500, detail="Failed to fetch test results from database."
        )
    finally:
        if conn is not None:
            conn.close()


@app.get("/results/{run_id}")
def get_run_details(run_id: int):
    """Fetches all details for a single, specific test run by its primary key ID."""
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
