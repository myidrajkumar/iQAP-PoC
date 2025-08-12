FROM mcr.microsoft.com/playwright/python:v1.53.0-noble
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN playwright install
CMD ["python", "agent.py"]