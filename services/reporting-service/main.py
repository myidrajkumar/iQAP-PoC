import os
import psycopg2
import asyncio
import json
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from collections import defaultdict
from datetime import date, timedelta
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

load_dotenv()

# --- Configurations ---
is_docker = os.environ.get("DOCKER_ENV") == "true"
if is_docker:
    DB_HOST = "iqap-postgres"
    REALTIME_SERVICE_URL = "http://realtime-service:8003"
else:
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    REALTIME_SERVICE_URL = os.getenv("REALTIME_SERVICE_URL", "http://localhost:8003")
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
                    artifacts_path VARCHAR(255),
                    visual_artifacts JSONB
                );
                """
            )
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='test_results' AND column_name='visual_artifacts'"
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE test_results ADD COLUMN visual_artifacts JSONB;"
                )
            conn.commit()
            cursor.close()
            print("Reporting Service: Database table 'test_results' is ready.")
            break
        except psycopg2.OperationalError:
            print("Reporting Service: PostgreSQL not ready yet. Waiting 5 seconds to retry...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"CRITICAL ERROR during startup: Could not initialize database table. {e}")
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

# --- Pydantic Models ---
class InitialRunRequest(BaseModel):
    objective: str
    test_case_id: str
    parameters: Optional[List[Dict[str, Any]]] = None

class FinalStatusRequest(BaseModel):
    status: str
    visual_status: str
    failure_reason: Optional[str] = None

# --- Helper Functions ---
def get_db_connection():
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)
        return conn
    except psycopg2.OperationalError as e:
        raise HTTPException(status_code=503, detail="Database service is unavailable.")

def process_daily_summary(rows, days):
    today = date.today()
    date_range = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    summary = {dt.strftime("%Y-%m-%d"): {"pass": 0, "fail": 0} for dt in date_range}
    for row in rows:
        day_str = row["day"].strftime("%Y-%m-%d")
        if day_str in summary:
            if row["status"] == "PASS": summary[day_str]["pass"] = row["count"]
            elif row["status"] == "FAIL": summary[day_str]["fail"] = row["count"]
    return [{"date": day, **counts} for day, counts in summary.items()]

# --- API Endpoints ---

@app.get("/results")
def get_test_results():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id, objective, status, visual_status, timestamp FROM test_results ORDER BY timestamp DESC LIMIT 100;")
        results = cursor.fetchall()
        cursor.close()
        return results
    finally:
        if conn is not None: conn.close()

@app.get("/results/{run_id}")
def get_run_details(run_id: int):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM test_results WHERE id = %s;", (run_id,))
        result = cursor.fetchone()
        cursor.close()
        if not result: raise HTTPException(status_code=404, detail=f"Test run with ID {run_id} not found.")
        return result
    finally:
        if conn is not None: conn.close()

@app.post("/results", status_code=201)
def create_initial_run(request: InitialRunRequest):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        objective = request.objective
        if request.parameters:
            dataset_name = request.parameters[0].get("dataset_name", "default")
            objective += f" ({dataset_name})"
        sql = "INSERT INTO test_results (objective, test_case_id, status, visual_status) VALUES (%s, %s, 'RUNNING', 'N/A') RETURNING *;"
        cursor.execute(sql, (objective, request.test_case_id))
        new_record = cursor.fetchone()
        conn.commit()
        cursor.close()
        return new_record
    finally:
        if conn is not None: conn.close()

@app.put("/results/{run_id}/final-status")
def update_final_run_status(run_id: int, request: FinalStatusRequest):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        sql = """
            UPDATE test_results
            SET status = %s, visual_status = %s, failure_reason = %s
            WHERE id = %s
            RETURNING *;
        """
        cursor.execute(sql, (request.status, request.visual_status, request.failure_reason, run_id))
        updated_record = cursor.fetchone()
        conn.commit()
        cursor.close()

        if updated_record:
            updated_record['timestamp'] = updated_record['timestamp'].isoformat()
            try:
                httpx.post(f"{REALTIME_SERVICE_URL}/notify/broadcast", json=updated_record, timeout=5)
                print(f"  [Notification] Sent final status broadcast for ID: {run_id}")
            except httpx.RequestError as e:
                print(f"  [Notification] Could not send final status broadcast: {e}")
        
        return {"status": "success", "message": f"Run {run_id} status updated."}
    except Exception as e:
        print(f"ERROR updating final status for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update final status.")
    finally:
        if conn is not None:
            conn.close()

@app.get("/stats/kpis")
def get_kpis(days: int = 7):
    """Calculates and returns key performance indicators for a given period."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT
                COUNT(*) AS total_runs,
                COUNT(*) FILTER (WHERE status = 'PASS') AS passed_runs
            FROM test_results
            WHERE timestamp >= NOW() - INTERVAL '%s days';
        """
        cursor.execute(query, (days,))
        data = cursor.fetchone()
        total_runs = data["total_runs"] or 0
        passed_runs = data["passed_runs"] or 0
        pass_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0
        return {"total_runs": total_runs, "pass_rate": round(pass_rate, 1)}
    except Exception as e:
        print(f"ERROR fetching KPIs: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch KPIs.")
    finally:
        if conn is not None: conn.close()

@app.get("/stats/daily_summary")
def get_daily_summary(days: int = 7):
    """Returns a daily breakdown of pass/fail counts for a given period."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT
                DATE(timestamp) AS day,
                status,
                COUNT(*) AS count
            FROM test_results
            WHERE timestamp >= NOW() - INTERVAL '%s days'
            AND status IN ('PASS', 'FAIL')
            GROUP BY DATE(timestamp), status
            ORDER BY day;
        """
        cursor.execute(query, (days,))
        rows = cursor.fetchall()
        summary = process_daily_summary(rows, days)
        return summary
    except Exception as e:
        print(f"ERROR fetching daily summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch daily summary.")
    finally:
        if conn is not None: conn.close()

@app.get("/")
def read_root():
    """Root endpoint for health checks."""
    return {"message": "iQAP Reporting Service is running."}