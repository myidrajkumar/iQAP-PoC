#!/bin/bash

python -m venv venv
# .\venv\Scripts\activate
source venv/Scripts/activate

# ai-orchestrator setup
pip install -r ./services/ai-orchestrator/requirements.txt

# discovery-service setup
pip install -r ./services/discovery-service/requirements.txt

# reporting-service setup
pip install -r ./services/reporting-service/requirements.txt

# realtime-service setup
pip install -r ./services/realtime-service/requirements.txt

# execution-orchestrator setup
pip install -r ./services/execution-orchestrator/requirements.txt

# execution-agent setup
pip install -r ./services/execution-agent/requirements.txt

# frontend setup
cd ./frontend/
npm install