<p align="center">
  <h1 align="center">🤖 Auto-Patch CI</h1>
  <p align="center">
    <strong>An autonomous, self-healing CI/CD pipeline powered by a multi-agent LLM swarm</strong>
  </p>
  <p align="center">
    <a href="#architecture">Architecture</a> •
    <a href="#how-it-works">How It Works</a> •
    <a href="#getting-started">Getting Started</a> •
    <a href="#usage">Usage</a> •
    <a href="#project-structure">Project Structure</a>
  </p>
</p>

---

## 🧠 What Is This?

**Auto-Patch CI** is a system that automatically detects, diagnoses, and patches failing CI/CD pipelines — without human intervention.

When a GitHub Actions workflow fails, a webhook fires into this system, kicking off a **multi-agent swarm** that:

1. **Triages** the error log to pinpoint the failing file and function
2. **Extracts** the faulty source code using AST parsing
3. **Engineers** a corrected patch using a large language model
4. **Tests** the patch inside an ephemeral Docker sandbox
5. **Retries** automatically if the fix doesn't pass (up to 3 iterations)

All LLM calls are funneled through a strict **token-bucket rate limiter** to stay within Groq's free-tier API limits.

---

## 🏗️ Architecture

```
GitHub Actions (Failure)
        │
        ▼
┌───────────────────┐
│  FastAPI Webhook   │  ◄── Receives workflow_run failure events
│    (main.py)       │
└────────┬──────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────┐
│              LangGraph State Machine (state_machine.py)    │
│                                                            │
│  ┌──────────┐   ┌────────────┐   ┌────────────┐           │
│  │ Triage   │──▶│ Extraction │──▶│ Engineer   │           │
│  │ Agent    │   │ Node (AST) │   │ Agent      │           │
│  │ (LLM)   │   │            │   │ (LLM)      │           │
│  └──────────┘   └────────────┘   └─────┬──────┘           │
│       ▲                                │                   │
│       │         ┌──────────────┐       │                   │
│       └─────────│  Test Node   │◀──────┘                   │
│     (on fail,   │  (Sandbox)   │                           │
│      retry ≤3)  └──────────────┘                           │
└────────────────────────────────────────────────────────────┘
         │
         ▼
   ✅ Patch Ready for PR
```

---

## ⚙️ How It Works

### 1. Webhook Ingestion — `main.py`
A **FastAPI** server listens for GitHub webhook payloads. When it receives a `workflow_run` event with `conclusion: failure`, it triggers the repair pipeline.

### 2. Triage Agent — `state_machine.py`
Uses **Llama 3.3 70B** (via Groq) with structured output to analyze the error log and identify:
- The **file path** containing the bug
- The **function name** that failed

### 3. Code Extraction — `parser.py`
Uses **Tree-sitter** to parse the identified Python file into an AST, then surgically extracts only the failing function's source code. This minimizes the context window sent to the LLM.

### 4. Engineer Agent — `state_machine.py`
A second **Llama 3.3 70B** call receives the error log + extracted function code and generates a corrected, drop-in replacement function.

### 5. Sandbox Testing — `sandbox.py`
The generated patch is tested in an **ephemeral Docker container** (or a local subprocess fallback):
- The workspace is mounted read-write
- The patched file is overlaid read-only
- `pytest` runs inside the container
- The container is destroyed immediately after

### 6. Retry Loop
If the test fails, the system routes back to the **Triage Agent** with the new error log. This loop runs up to **3 iterations** before giving up.

### 7. Rate Limiting — `rate_limiter.py`
An **async token-bucket rate limiter** enforces Groq's 30 RPM free-tier limit. Every LLM call must first `await groq_rate_limiter.acquire()` before proceeding.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Docker** (optional — falls back to local subprocess sandboxing)
- **Groq API Key** ([get one free](https://console.groq.com/keys))

### Installation

```bash
# Clone the repository
git clone https://github.com/kartik0905/auto-patch-ci.git
cd auto-patch-ci

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy the example env file and add your API key
cp .env.example .env
```

Edit `.env` and set your Groq API key:

```
GROQ_API_KEY=gsk_your_actual_api_key_here
```

---

## 📖 Usage

### Run the Webhook Server

```bash
python main.py
```

The FastAPI server starts at `http://localhost:8000`. Configure your GitHub repository to send webhook events to this endpoint.

### Run the Self-Healing Pipeline Directly

To test the full agent swarm locally (without GitHub webhooks):

```bash
python test_pipeline.py
```

This will:
1. Run `pytest test_math.py` to generate a real error log (from the intentionally buggy `math_utils.py`)
2. Feed the error log into the LangGraph state machine
3. Watch the Triage → Extract → Engineer → Test loop execute in real time

### API Endpoints

| Method | Endpoint    | Description                               |
|--------|-------------|-------------------------------------------|
| POST   | `/webhook`  | Receives GitHub Actions webhook payloads  |

---

## 📁 Project Structure

```
.
├── main.py              # FastAPI webhook server (entry point)
├── state_machine.py     # LangGraph agent swarm (Triage → Extract → Engineer → Test)
├── parser.py            # Tree-sitter AST parser for surgical code extraction
├── sandbox.py           # Ephemeral Docker sandbox with local fallback
├── rate_limiter.py      # Async token-bucket rate limiter (Groq 30 RPM)
├── math_utils.py        # Intentionally buggy module (demo target)
├── test_math.py         # Pytest tests for math_utils (triggers failures)
├── test_pipeline.py     # End-to-end pipeline test script
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
└── .gitignore           # Git ignore rules
```

---

## 🛠️ Tech Stack

| Component         | Technology                                      |
|--------------------|-------------------------------------------------|
| **Web Framework**  | FastAPI + Uvicorn                               |
| **Agent Orchestration** | LangGraph (StateGraph)                     |
| **LLM Provider**   | Groq (Llama 3.3 70B Versatile)                 |
| **Code Parsing**   | Tree-sitter (Python bindings)                   |
| **Sandboxing**     | Docker SDK for Python (with subprocess fallback)|
| **Rate Limiting**  | Custom async token-bucket implementation        |
| **Configuration**  | python-dotenv                                   |

---

## 🔒 Security

- **Ephemeral containers** — sandbox containers are destroyed immediately after test execution
- **Read-only patch overlay** — patched files are mounted as read-only inside containers
- **No persistent state** — each repair cycle is fully isolated
- **Rate-limited API calls** — prevents accidental API abuse

---

## 📝 License

This project is open source. Feel free to use, modify, and distribute.

---

<p align="center">
  Built with ❤️ using LangGraph, Groq, and Tree-sitter
</p>
