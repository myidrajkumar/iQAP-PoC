#!/bin/bash

LOG_FILE_AI_ORCHESTRATOR="logs/ai_orchestrator.log"
LOG_FILE_DISCOVERY="logs/discovery.log"
LOG_FILE_REPORTING="logs/reporting.log"
LOG_FILE_REALTIME="logs/realtime.log"
LOG_FILE_EXECUTION_ORCHESTRATOR="logs/execution_orchestrator.log"
LOG_FILE_EXECUTION_AGENT="logs/execution_agent.log"
LOG_FILE_FRONTEND="logs/frontend.log"

mkdir -p logs

source venv/Scripts/activate

uvicorn main:app --port 8000 --reload --app-dir ./services/ai-orchestrator/ > "$LOG_FILE_AI_ORCHESTRATOR" 2>&1 &
echo "Started uvicorn for AI Orchestrator. Logs in $LOG_FILE_AI_ORCHESTRATOR"

uvicorn main:app --port 8001 --reload --app-dir ./services/discovery-service/ > "$LOG_FILE_DISCOVERY" 2>&1 &
echo "Started uvicorn for Discovery Service. Logs in $LOG_FILE_DISCOVERY"

uvicorn main:app --port 8002 --reload --app-dir ./services/reporting-service/ > "$LOG_FILE_REPORTING" 2>&1 &
echo "Started uvicorn for Reporting Service. Logs in $LOG_FILE_REPORTING"

uvicorn main:app --port 8003 --reload --app-dir ./services/realtime-service/ > "$LOG_FILE_REALTIME" 2>&1 &
echo "Started uvicorn for Realtime Service. Logs in $LOG_FILE_REALTIME"

python -u ./services/execution-orchestrator/orchestrator.py > "$LOG_FILE_EXECUTION_ORCHESTRATOR" 2>&1 &
echo "Started uvicorn for Execution Orchestrator. Logs in $LOG_FILE_EXECUTION_ORCHESTRATOR"

python -u ./services/execution-agent/agent.py > "$LOG_FILE_EXECUTION_AGENT" 2>&1 &
echo "Started uvicorn for Execution Agent. Logs in $LOG_FILE_EXECUTION_AGENT"

npm start --prefix ./frontend/  > "$LOG_FILE_FRONTEND" 2>&1 &
echo "Started npm for frontend. Logs in $LOG_FILE_FRONTEND"

wait

echo "All services have stopped."
