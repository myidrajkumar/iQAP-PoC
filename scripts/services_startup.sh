# Define paths for log files using Join-Path for robustness
$logDir = "logs"
$LOG_FILE_AI_ORCHESTRATOR = Join-Path $PSScriptRoot $logDir "ai_orchestrator.log"
$LOG_FILE_DISCOVERY = Join-Path $PSScriptRoot $logDir "discovery.log"
$LOG_FILE_REPORTING = Join-Path $PSScriptRoot $logDir "reporting.log"
$LOG_FILE_REALTIME = Join-Path $PSScriptRoot $logDir "realtime.log"
$LOG_FILE_EXECUTION_ORCHESTRATOR = Join-Path $PSScriptRoot $logDir "execution_orchestrator.log"
$LOG_FILE_EXECUTION_AGENT = Join-Path $PSScriptRoot $logDir "execution_agent.log"
$LOG_FILE_FRONTEND = Join-Path $PSScriptRoot $logDir "frontend.log"

# Create the logs directory if it doesn't exist
if (-not (Test-Path (Join-Path $PSScriptRoot $logDir))) {
    New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot $logDir)
}

# Activate the Python virtual environment
try {
    . (Join-Path $PSScriptRoot '..\venv\Scripts\Activate.ps1')
} catch {
    Write-Host "Failed to activate Python virtual environment. Please run the setup script first."
    exit 1
}

# Array to keep track of all started processes
$processes = @()

try {
    # Start AI Orchestrator
    $command = "uvicorn main:app --port 8000 --reload --app-dir ./services/ai-orchestrator/ *>> '$LOG_FILE_AI_ORCHESTRATOR'"
    $processes += Start-Process -FilePath "powershell.exe" -ArgumentList "-Command", $command -WindowStyle Hidden -PassThru
    Write-Host "Started uvicorn for AI Orchestrator. Logs in $LOG_FILE_AI_ORCHESTRATOR"
    Start-Sleep -Seconds 1

    # Start Discovery Service
    $command = "uvicorn main:app --port 8001 --reload --app-dir ./services/discovery-service/ *>> '$LOG_FILE_DISCOVERY'"
    $processes += Start-Process -FilePath "powershell.exe" -ArgumentList "-Command", $command -WindowStyle Hidden -PassThru
    Write-Host "Started uvicorn for Discovery Service. Logs in $LOG_FILE_DISCOVERY"
    Start-Sleep -Seconds 1

    # Start Reporting Service
    $command = "uvicorn main:app --port 8002 --reload --app-dir ./services/reporting-service/ *>> '$LOG_FILE_REPORTING'"
    $processes += Start-Process -FilePath "powershell.exe" -ArgumentList "-Command", $command -WindowStyle Hidden -PassThru
    Write-Host "Started uvicorn for Reporting Service. Logs in $LOG_FILE_REPORTING"
    Start-Sleep -Seconds 1

    # Start Realtime Service
    $command = "uvicorn main:app --port 8003 --reload --app-dir ./services/realtime-service/ *>> '$LOG_FILE_REALTIME'"
    $processes += Start-Process -FilePath "powershell.exe" -ArgumentList "-Command", $command -WindowStyle Hidden -PassThru
    Write-Host "Started uvicorn for Realtime Service. Logs in $LOG_FILE_REALTIME"
    Start-Sleep -Seconds 1

    # Start Execution Agent
    $command = "uvicorn main:app --port 8004 --reload --app-dir ./services/execution-agent/ *>> '$LOG_FILE_EXECUTION_AGENT'"
    $processes += Start-Process -FilePath "powershell.exe" -ArgumentList "-Command", $command -WindowStyle Hidden -PassThru
    Write-Host "Started uvicorn for Execution Agent. Logs in $LOG_FILE_EXECUTION_AGENT"
    Start-Sleep -Seconds 1

    # Start Frontend
    $command = "npm start --prefix ./frontend/ *>> '$LOG_FILE_FRONTEND'"
    $processes += Start-Process -FilePath "powershell.exe" -ArgumentList "-Command", $command -WindowStyle Hidden -PassThru
    Write-Host "Started npm for frontend. Logs in $LOG_FILE_FRONTEND"

    Write-Host "`nAll services are running in the background."
    Write-Host "Press Ctrl+C in this window to stop all services."
    
    Wait-Process -Id ($processes.Id)

}
finally {
    Write-Host "`nStopping all services..."
    $processes | ForEach-Object {
        if ($_.HasExited -eq $false) {
            Write-Host "Stopping process with ID $($_.Id)..."
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "All services have been stopped."
}