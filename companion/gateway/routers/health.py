"""
Health check router for the AI Companion System.
Provides system monitoring endpoints for uptime, service status, and performance metrics.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import asyncio
import time
import logging

from ..database import DatabaseManager
from ..utils.scheduler import get_scheduler
from ..services.groq_client import GroqClient
from ..services.chutes_client import ChutesClient
from ..main import get_db, get_groq, get_chutes

router = APIRouter(tags=["health"])

# Configure logger
logger = logging.getLogger(__name__)


@router.get("/", response_model=Dict[str, Any])
async def health_check():
    """
    Basic health check endpoint.
    Returns system status and basic information.
    """
    return {
        "status": "healthy",
        "message": "AI Companion Gateway is running",
        "timestamp": time.time(),
        "version": "1.0.0"
    }


@router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check(
    db: DatabaseManager = Depends(get_db),
    groq_client: GroqClient = Depends(get_groq),
    chutes_client: ChutesClient = Depends(get_chutes)
):
    """
    Detailed health check with service-specific status.
    Checks connectivity to all dependent services.
    """
    services_status = {}
    
    # Check database connectivity
    try:
        start_time = time.time()
         db_health = await db.health_check()
        response_time = time.time() - start_time
         services_status["database"] = {
             "status": "healthy" if db_health else "unhealthy",
            "response_time": response_time,
             "details": "Connected" if db_health else "Connection failed"
         }
    except Exception as e:
        services_status["database"] = {
            "status": "unhealthy",
            "error": str(e),
            "details": "Exception during database health check"
        }
    
    # Check Groq API connectivity
    try:
        start_time = time.time()
        groq_health = await groq_client.health_check()
        response_time = time.time() - start_time
        services_status["groq_api"] = {
            "status": "healthy" if groq_health else "unhealthy",
            "response_time": response_time,
            "details": "Connected" if groq_health else "Connection failed"
        }
    except Exception as e:
        services_status["groq_api"] = {
            "status": "unhealthy",
            "error": str(e),
            "details": "Exception during Groq API health check"
        }
    
    # Check Chutes API connectivity
    try:
        start_time = time.time()
        chutes_health = await chutes_client.health_check()
        response_time = time.time() - start_time
        services_status["chutes_api"] = {
            "status": "healthy" if chutes_health else "unhealthy",
            "response_time": response_time,
            "details": "Connected" if chutes_health else "Connection failed"
        }
    except Exception as e:
        services_status["chutes_api"] = {
            "status": "unhealthy",
            "error": str(e),
            "details": "Exception during Chutes API health check"
        }
    
    # Check scheduler status
    try:
        scheduler = await get_scheduler()
        if scheduler:
            scheduler_status = scheduler.get_all_jobs_status()
            services_status["scheduler"] = {
                "status": "healthy",
                "active_jobs": len(scheduler_status),
                "details": f"Scheduler running with {len(scheduler_status)} jobs"
            }
        else:
            services_status["scheduler"] = {
                "status": "unhealthy",
                "details": "Scheduler not initialized"
            }
    except Exception as e:
        services_status["scheduler"] = {
            "status": "unhealthy",
            "error": str(e),
            "details": "Exception during scheduler health check"
        }
    
    # Overall status
    all_services_healthy = all(
        status.get("status") == "healthy" 
        for status in services_status.values()
    )
    
    return {
        "status": "healthy" if all_services_healthy else "degraded",
        "timestamp": time.time(),
        "services": services_status,
        "overall_healthy": all_services_healthy
    }


@router.get("/metrics", response_model=Dict[str, Any])
async def system_metrics():
    """
    System performance metrics including request counts, error rates, and resource usage.
    """
    # TODO: Replace with actual metrics collection from a proper metrics system (Prometheus, StatsD, etc.)
    # For now, returning mock data with a note that this is not real metrics
    return {
        "status": "mock_data",
        "note": "Replace with actual metrics collection in production",
        "timestamp": time.time(),
        "metrics": {
            "requests_per_minute": 42,  # This would come from a metrics system
            "error_rate_percentage": 0.0,
            "average_response_time_ms": 120,
            "active_connections": 10,
            "memory_usage_mb": 150,  # This would come from system monitoring
        }
    }


@router.get("/ready", response_model=Dict[str, Any])
async def readiness_check(db: DatabaseManager = Depends(get_db)):
    """
    Readiness check for container orchestration.
    Determines if the service is ready to accept traffic.
    """
    try:
        # Check if database is accessible
        db_ready = await db.health_check()
        if not db_ready:
            return {
                "status": "not_ready",
                "reason": "Database not accessible"
            }

        # If we get here, service is ready
        return {
            "status": "ready",
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "status": "not_ready",
            "reason": f"Exception during readiness check: {str(e)}"
        }


@router.get("/liveness", response_model=Dict[str, Any])
async def liveness_check():
    """
    Liveness check for container orchestration.
    Determines if the service itself is alive and responding.
    """
    return {
        "status": "alive",
        "timestamp": time.time(),
        "checks": {
            "api_responding": True,
            "basic_processing": True
        }
    }