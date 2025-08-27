import json
import logging
from fastapi import APIRouter, HTTPException, Body
from schemas.test_case import GenerationRequest, GenerationResponse
from services import ai_service, discovery_service, messaging_service
import psycopg2
from psycopg2.extras import RealDictCursor
from core.config import settings
import os

logger = logging.getLogger(__name__)
router = APIRouter()

# --- DB connection details ---
if settings.IS_DOCKER:
    DB_HOST = "iqap-postgres"
else:
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")

# --- Function to create initial record ---
def create_initial_record(test_case: dict):
    conn = None
    new_run_id = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        objective = test_case.get('objective', 'No objective provided')
        if test_case.get('parameters'):
            dataset_name = test_case['parameters'][0].get('dataset_name', 'default')
            objective += f" ({dataset_name})"

        test_case_id = test_case.get('test_case_id', 'N/A')
        
        sql = """
            INSERT INTO test_results (objective, test_case_id, status, timestamp)
            VALUES (%s, %s, 'RUNNING', NOW())
            RETURNING id;
        """
        cursor.execute(sql, (objective, test_case_id))
        result = cursor.fetchone()
        if result:
            new_run_id = result['id']
            print(f"  [DB] Created initial record with ID: {new_run_id}")
            
        conn.commit()
        cursor.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"  [DB] Orchestrator Error: Could not create initial record: {error}")
    finally:
        if conn is not None:
            conn.close()
    return new_run_id


@router.get("/")
def read_root():
    return {"message": "iQAP AI Orchestrator is running."}


@router.post("/generate-test-case", response_model=dict)
async def generate_test_case_endpoint(request: GenerationRequest):
    """
    Generates a test case and returns it for user review.
    """
    logger.info("Received request to GENERATE test for URL: %s", request.target_url)
    try:
        ui_blueprint_string = await discovery_service.get_ui_blueprint(request.target_url)
        ui_blueprint_json = json.loads(ui_blueprint_string)
        generated_test_case = ai_service.ai_service.generate_test_case(
            request.requirement, ui_blueprint_string
        )
        generated_test_case["ui_blueprint"] = ui_blueprint_json.get("elements", [])
        generated_test_case["target_url"] = request.target_url
        logger.info("Successfully generated test case. Returning to frontend for review.")
        return generated_test_case
    except Exception as e:
        logger.fatal(f"FATAL ERROR in generation process: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@router.post("/publish-test-case", response_model=GenerationResponse)
async def publish_test_case_endpoint(test_case: dict = Body(...)):
    """
    Creates the initial DB record, publishes the job, and returns the new run_id.
    """
    logger.info("Received request to PUBLISH test case ID: %s", test_case.get("test_case_id"))
    try:
        new_run_id = create_initial_record(test_case)
        if not new_run_id:
            raise HTTPException(status_code=500, detail="Failed to create initial test run record in database.")
        
        test_case['db_run_id'] = new_run_id
        messaging_service.publish_to_rabbitmq(test_case)
        
        return GenerationResponse(
            message="Test Case Execution Job Published!",
            test_case_id=test_case.get("test_case_id"),
            run_id=new_run_id
        )
    except Exception as e:
        logger.error(f"Failed to publish test case: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to publish job.")