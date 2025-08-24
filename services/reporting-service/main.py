import os
import psycopg2
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# --- Database Connection Details (from environment variables) ---
is_docker = os.environ.get("DOCKER_ENV") == "true"

if is_docker:
    DB_HOST = "iqap-postgres"
else:
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Reporting Service: Lifespan startup event...")
    conn = None
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
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    failure_reason TEXT,
                    artifacts_path VARCHAR(255)
                );
            """
            )
            # --- Check and add new columns if they don't exist (for backward compatibility) ---
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='test_results' AND column_name='failure_reason'"
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE test_results ADD COLUMN failure_reason TEXT;"
                )

            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='test_results' AND column_name='artifacts_path'"
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE test_results ADD COLUMN artifacts_path VARCHAR(255);"
                )

            conn.commit()
            cursor.close()
            print("Reporting Service: Database table 'test_results' is ready.")
            break

        except psycopg2.OperationalError:
            print(
                "Reporting Service: PostgreSQL not ready yet. Waiting 5 seconds to retry..."
            )
            await asyncio.sleep(5)
        except Exception as e:
            print(
                f"CRITICAL ERROR during startup: Could not initialize database table. {e}"
            )
            await asyncio.sleep(5)
        finally:
            if conn is not None:
                conn.close()

    yield
    print("Reporting Service: Lifespan shutdown event...")


app = FastAPI(lifespan=lifespan)

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
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
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
        raise HTTPException(
            status_code=500, detail="Failed to fetch test results from database."
        )
    finally:
        if conn is not None:
            conn.close()


# This endpoint is now more important than ever for the details page
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
