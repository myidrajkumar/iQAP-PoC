# iQAP - The Intelligent Quality Assurance Platform

iQAP is a self-learning, integrated platform that autonomously discovers application features, generates strategic test plans, executes them intelligently, and provides predictive insights to development teams. Its core mission is to reduce human intervention to a minimum, focusing human expertise on complex problem-solving rather than repetitive tasks.

This repository contains the Proof of Concept (PoC) for the iQAP platform, demonstrating a full-stack, microservices-based architecture for AI-driven test automation.

## ✨ Core Features

* **AI-Powered Test Generation**: Uses Google's Gemini Pro to convert plain English business requirements into structured, executable test cases.
* **Autonomous Application Discovery**: A `discovery-service` crawls a target URL to create a "UI Blueprint" of all interactive elements, providing the AI with the necessary context.
* **Microservices Architecture**: A fully containerized system with distinct services for the frontend, orchestration, discovery, execution, and reporting, ensuring scalability and separation of concerns.
* **Message-Driven Execution**: Leverages RabbitMQ as a message broker to create a resilient, asynchronous workflow for test generation and execution.
* **Visual Regression Testing**: The `execution-agent` takes screenshots and compares them against baselines stored in MinIO, automatically detecting visual changes.
* **Persistent Test Reporting**: All test run results are stored in a PostgreSQL database and can be viewed through the `reporting-service` and the frontend UI.
* **Developer-Friendly**: The entire stack is managed with a single `docker-compose` file for easy setup and teardown.

## 🛠️ Technology Stack

| Category           | Technology                                                                          |
| ------------------ | ----------------------------------------------------------------------------------- |
| **Frontend**       | React.js, Axios, JavaScript (ES6+)                                                  |
| **Backend**        | Python, FastAPI                                                                     |
| **AI Integration** | Google Gemini Pro (`google-generativeai`)                                           |
| **Web Automation** | Playwright                                                                          |
| **Infrastructure** | Docker, Docker Compose                                                              |
| **Database**       | PostgreSQL, pgAdmin                                                                 |
| **Message Broker** | RabbitMQ                                                                            |
| **Object Storage** | MinIO (for visual test baselines)                                                   |

## 🏗️ System Architecture

The iQAP platform is built on a distributed, event-driven architecture. Each service has a specific responsibility, and they communicate through REST APIs and a central message queue.

![iQAP Architecture Diagram](./docs/iqap-architecture.svg)

### Service Responsibilities

* **`frontend`**: The React-based user interface where users can input a target URL and a business requirement to trigger a test run.
* **`ai-orchestrator`**: The brain of the operation. It receives user requests, calls the `discovery-service` to map the application, uses Gemini AI to generate a test script, and publishes the final job to RabbitMQ.
* **`discovery-service`**: A FastAPI service that uses Playwright to visit a URL and extract a JSON "blueprint" of all interactive UI elements.
* **`execution-orchestrator`**: A simple but crucial service that listens for newly generated test cases and forwards them to the queue for the execution agents. This decoupling allows for future features like load balancing or scheduling.
* **`execution-agent`**: The worker. It picks up test jobs, launches a Playwright browser, executes the steps, performs visual comparisons against baselines in MinIO, and writes the final results to the PostgreSQL database.
* **`reporting-service`**: A FastAPI service that provides API endpoints to query test results from the PostgreSQL database.
* **`postgres`**, **`rabbitmq`**, **`minio`**: The core infrastructure services providing data persistence, messaging, and object storage.

## 🚀 Getting Started

Follow these instructions to get the entire iQAP platform running on your local machine.

### Prerequisites

* **Docker and Docker Compose**: Ensure they are installed and running on your system. [Install Docker](https://docs.docker.com/get-docker/).
* **Google Gemini API Key**: You need an API key from Google AI Studio. [Get API Key](https://aistudio.google.com/app/apikey).

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd <your-repository-folder>
```

### 2. Create the Environment File

Create a file named `.env` in the root of the project directory. It's recommended to copy the contents of `.env.example` (if provided) or use the template below and fill in the required values.

#### `.env` Template

```ini
# --- Gemini AI Configuration ---
# Get your API key from https://aistudio.google.com/app/apikey
GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"
GEMINI_MODEL_NAME="gemini-1.5-flash-latest"
GEMINI_TEMPERATURE=0.0

# --- PostgreSQL Configuration ---
POSTGRES_DB=iqap_db
POSTGRES_USER=iqap_user
POSTGRES_PASSWORD=a_very_secret_password
POSTGRES_HOST=localhost # Used for local scripts, overridden by docker-compose
POSTGRES_PORT=5432

# --- RabbitMQ Configuration ---
RABBITMQ_DEFAULT_USER=rabbit_user
RABBITMQ_DEFAULT_PASS=rabbit_password
RABBITMQ_HOST=localhost # Used for local scripts, overridden by docker-compose

# --- MinIO Object Storage Configuration ---
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
```

### 3. Build and Run the Stack

From the root directory, run the following command. This will pull the necessary images, build your custom service images, and start all containers.

```bash
docker-compose up --build
```

The initial build may take a few minutes. Once it's complete, the services will be available at the following URLs:

* **iQAP Frontend**: [http://localhost:3000](http://localhost:3000)
* **RabbitMQ Management**: [http://localhost:15672](http://localhost:15672) (Login with user/pass from your `.env` file)
* **MinIO Console**: [http://localhost:9001](http://localhost:9001) (Login with user/pass from your `.env` file)
* **pgAdmin 4**: [http://localhost:8900](http://localhost:8900) (Login with email/pass from `docker-compose.yml`)

## 💡 How to Use

1. Navigate to the **iQAP Frontend** at `http://localhost:3000`.
2. The form will be pre-populated with a sample URL (`https://www.saucedemo.com`) and a business requirement.
3. Click the **"Generate & Run Test"** button.
4. Observe the status message below the button as the system works.
5. After a short while, the **Test Run History** on the right will update with the results of your test. The first run for a test case will have a `BASELINE_CREATED` visual status. Subsequent runs will show `PASS` or `FAIL`.

---

## 🖥️ Debugging with Headful (UI) Mode

Your current configuration is perfectly set up for running headless tests *within Docker*, which is the best practice for CI/CD and automated environments. The line `IS_HEADLESS = True` when `is_docker` is detected in `agent.py` is correct because you cannot easily render a UI from a standard container.

However, for local development and debugging, you might want to see the browser in action. To do this, you can run the `execution-agent` script directly on your host machine while the rest of the stack remains in Docker.

**Here is the recommended workflow:**

1. **Start Only the Infrastructure:**
    First, start only the necessary background services using Docker Compose.

    ```bash
    docker-compose up -d postgres rabbitmq minio
    ```

2. **Stop the Dockerized Agent (if running):**
    If the full stack is already running, you need to stop the agent container so it doesn't compete for jobs.

    ```bash
    docker-compose stop execution-agent
    ```

3. **Set Up a Local Environment for the Agent:**
    Open a new terminal window and navigate to the agent's directory.

    ```bash
    cd services/execution-agent
    ```

    Create a virtual environment and install the dependencies.

    ```bash
    # Create virtual environment
    python -m venv venv

    # Activate it (Windows)
    .\venv\Scripts\activate

    # Activate it (macOS/Linux)
    source venv/bin/activate

    # Install dependencies
    pip install -r requirements.txt
    ```

4. **Install Playwright Browsers:**
    This only needs to be done once.

    ```bash
    playwright install
    ```

5. **Run the Agent in Headful Mode:**

    Now, run the agent script from your terminal. It will pick up the environment variables from the `.env` file and connect to the Dockerized infrastructure.

    ```bash
    python agent.py
    ```

You will now see the agent connect to RabbitMQ. When you trigger a test from the frontend, a Chrome browser window will appear on your screen and you can watch the test execute in real-time.