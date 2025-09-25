from fastapi import APIRouter, HTTPException
from app.core.database import db
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
    """Check system health status"""
    try:
        # Check MongoDB connection
        await db.client.server_info()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "healthy",
            "database": db_status
        }
    }