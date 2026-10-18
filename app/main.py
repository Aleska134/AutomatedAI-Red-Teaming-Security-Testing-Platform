from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.database import ping_database
from app.routers import router as api_router  # <-- Importamos nuestro router
from app.services.accounts import ensure_admin_user
from app.services.commerce import seed_commerce_data

app = FastAPI(
    title="Automated AI Red Teaming Platform API",
    description="REST API layer to trigger and analyze bot-vs-bot security simulations.",
    version="1.0.0"
)

# Incluimos las rutas del Defender y de autenticación en la aplicación
app.include_router(api_router)
app.include_router(auth_router)

@app.on_event("startup")
async def startup_event():
    """Executes automatically when the FastAPI server starts up."""
    print("🚀 Initializing system services...")
    await ping_database()
    seed_commerce_data()
    ensure_admin_user()

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "AI Red Teaming API is running smoothly."
    }