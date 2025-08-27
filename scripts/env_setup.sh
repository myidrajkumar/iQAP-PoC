python -m venv venv

.\venv\Scripts\Activate

pip install -r ./services/ai-orchestrator/requirements.txt
pip install -r ./services/discovery-service/requirements.txt
pip install -r ./services/reporting-service/requirements.txt
pip install -r ./services/realtime-service/requirements.txt
pip install -r ./services/execution-agent/requirements.txt

cd ./frontend/
npm install
