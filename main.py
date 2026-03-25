from fastapi import FastAPI, Request
from rate_limiter import groq_rate_limiter
import uvicorn
import logging
from dotenv import load_dotenv

# Load environment variables (like GROQ_API_KEY) from .env file
load_dotenv()

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Self-Healing CI/CD Pipeline",
    description="Webhook server for receiving failing GitHub Action payloads and triggering an autonomous repair swarm."
)

@app.post("/webhook")
async def github_webhook(request: Request):
    """
    Receives GitHub Actions webhook payloads.
    Relevant events: workflow_run (when action=completed and conclusion=failure).
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}
        
    action = payload.get("action")
    workflow_run = payload.get("workflow_run", {})
    conclusion = workflow_run.get("conclusion")
    
    logger.info(f"Received webhook payload: action={action}, conclusion={conclusion}")
    
    if action == "completed" and conclusion == "failure":
        logger.info("Failing GitHub Action detected. Initiating repair sequence...")
        # Note: In Phase 2, the LangGraph swarm (Triage & Engineer agents) will be triggered here.
        # Every call made to the Groq API by those agents will be wrapped with an `await groq_rate_limiter.acquire()`.
        # For demonstration in Phase 1, we acquire a token to simulate the rate limiting point.
        await groq_rate_limiter.acquire()
        logger.info("Successfully acquired token from Groq rate limiter. Ready to call LLM.")
        
        return {"status": "repair_sequence_initiated"}
        
    return {"status": "ignored", "message": "Event not related to a failing workflow run"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
