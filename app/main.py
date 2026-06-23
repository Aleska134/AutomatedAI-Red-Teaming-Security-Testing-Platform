# from fastapi import FastAPI, HTTPException
# from app.schemas import SimulationRequest, AuditReport
# from app.services.orchestrator import run_redteam_simulation

# app = FastAPI(
#     title="AI Red Teaming & Security Testing Platform API",
#     description="Backend engine to simulate automated linguistic attacks against LLM agents.",
#     version="1.0.0"
# )

# @app.get("/")
# def read_root():
#     return {"status": "online", "message": "AI Red Teaming API is running smoothly."}

# @app.post("/api/test-session", response_model=AuditReport)
# async def trigger_simulation(payload: SimulationRequest):
#     """
#     Triggers an automated Bot-vs-Bot simulation session and returns 
#     the full structured cybersecurity audit report.
#     """
#     try:
#         # Run the orchestrator with the number of turns requested by the user
#         report = await run_redteam_simulation(turns=payload.turns)
#         return report
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


from fastapi import FastAPI
from app.database import ping_database

app = FastAPI(
    title="Automated AI Red Teaming Platform API",
    description="REST API layer to trigger and analyze bot-vs-bot security simulations.",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    """Executes automatically when the FastAPI server starts up."""
    print("🚀 Initializing system services...")
    await ping_database()

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "AI Red Teaming API is running smoothly."
    }
