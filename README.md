# iQAP - Intelligent Quality Assurance Platform (Proof of Concept)

This repository contains the foundational codebase for the iQAP Proof of Concept. Our mission is to build an AI-driven asset that transforms software testing from a manual bottleneck into an autonomous, intelligent process.

This PoC demonstrates the core "plug and play" flow: converting a plain English requirement into a structured JSON test case, which can then be executed by a self-healing agent against any web application.

## Core Concepts Demonstrated

*   **Microservices Architecture:** The system is broken into independent services (Frontend, AI Orchestrator, Execution Agent), orchestrated by Docker Compose.
*   **Model-Context Protocol (MCP):** The AI Orchestrator simulates the MCP pattern by preparing a detailed context before generating the test case, ensuring a reliable, structured output.
*   **Technology Agnosticism:** The Execution Agent runs tests against a public website (`saucedemo.com`) to prove it does not need access to the target application's source code.

## PoC Scope (What this code does)

*   **✅ A web interface** to input requirements.
*   **✅ An AI service that simulates** generating a test case from the requirement.
*   **✅ An execution script that can run** the generated test case using Playwright.
*   **✅ A demonstration of basic self-healing** logic.

## What is NOT included in this PoC

*   ❌ **Real LLM API calls:** The AI response is currently mocked to ensure this PoC can run anywhere without API keys.
*   ❌ **Message Queue:** Services communicate directly via API calls for simplicity.
*   ❌ **Databases:** Test cases are not persisted.
*   ❌ **Discovery Service:** The UI "blueprint" is hardcoded in the AI service for this demo.

## Project Structure

```iQAP-PoC/
├── docker-compose.yml              # The master file to run all services
│
├── frontend/                       # The user interface (React)
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── App.css
│       └── App.js
│
└── services/                       # All backend microservices
    ├── ai-orchestrator/            # The MCP Brain (Python/FastAPI)
    │   ├── Dockerfile
    │   ├── requirements.txt
    │   └── main.py
    │
    └── execution-agent/            # The Test Runner (Python/Playwright)
        ├── Dockerfile
        ├── requirements.txt
        └── agent.py
```

## Prerequisites

*   [Docker](https://www.docker.com/products/docker-desktop/) installed and running on your machine.

## How to Run the PoC

Follow these steps to get the entire platform running locally.

**1. Create the Project Structure:**
Create the folders and files exactly as laid out in the "Project Structure" section above.

**2. Build and Run with Docker Compose:**
Open a terminal in the root `iQAP-PoC/` directory and run the following command:

```bash
docker-compose up --build -d
```

This command will:
*   Build the Docker images for the frontend and the backend services.
*   Start all the services.
*   You will see logs from all services in your terminal.

**3. Test the AI Generation Flow:**
*   Open your web browser and navigate to: **`http://localhost:3000`**
*   You should see the iQAP web interface.
*   Click the **"Generate Test Case"** button. The UI will show a loading state, and then display the structured JSON test case returned from the AI Orchestrator service.

**4. Test the Execution Agent Flow:**
*   Open a **new terminal window** (leave the other one running).
*   Navigate to the root `iQAP-PoC/` directory.
*   Execute the agent script inside its container with the following command:

```bash
docker-compose exec execution-agent python agent.py
```

*   You will see the Playwright script output in your terminal. It will log each step as it navigates the `saucedemo.com` website, enters credentials, clicks login, and verifies the result.

## Next Steps (Roadmap)

1.  Integrate a real LLM API in the `ai-orchestrator`.
2.  Implement a real Discovery Service to crawl target URLs.
3.  Add a Message Queue (RabbitMQ) for asynchronous job processing.
4.  Add a PostgreSQL database to persist test cases and results.