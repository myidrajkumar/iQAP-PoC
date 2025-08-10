# Use the official Playwright image from Microsoft for reliability
FROM mcr.microsoft.com/playwright/python:v1.44.0

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# This installs the necessary browser binaries inside the container
RUN playwright install