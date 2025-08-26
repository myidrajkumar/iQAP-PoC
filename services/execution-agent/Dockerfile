FROM mcr.microsoft.com/playwright/python:v1.53.0-noble

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

RUN playwright install

CMD ["python", "agent.py"]