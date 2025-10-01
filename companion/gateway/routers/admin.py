"""
Admin router for the AI Companion System.
Provides protected API endpoints for system administration, monitoring, and maintenance.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import asyncio

from ..models.user import UserProfile
from ..models.personality import PersonalitySnapshot, PADState
from ..models.interaction import InteractionRecord
from ..services.user_service import UserService
from ..services.personality_engine import PersonalityEngine
from ..services.memory_manager import MemoryManager
from ..database import DatabaseManager
from ..utils.scheduler import SchedulerService
from ..utils.background import BackgroundServiceManager
from ..utils.exceptions import UserNotFoundError

# Import dependency functions from main
from ..main import (
    get_users, get_personality, get_memory, get_db, 
    get_scheduler, get_background
)

router = APIRouter(tags=["admin"])

logger = logging.getLogger(__name__)


@router.get("/users", response_model=Dict[str, Any])
async def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    user_service: UserService = Depends(get_users)
):
    """
    Get a paginated list of all users in the system.
    Includes user statistics and status information.
    """
    try:
        users = await user_service.get_all_users(skip=skip, limit=limit)
        total_users = await user_service.get_total_user_count()
        
        return {
            "users": users,
            "total_users": total_users,
            "skip": skip,
            "limit": limit,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats", response_model=Dict[str, Any])
async def get_system_stats(
    user_service: UserService = Depends(get_users),
    memory_manager: MemoryManager = Depends(get_memory)
):
    """
    Get comprehensive system statistics.
    Includes user counts, memory usage, interaction counts, and system health.
    """
    try:
        # Get user statistics
        total_users = await user_service.get_total_user_count()
        active_users_24h = await user_service.get_active_users_count(hours=24)
        active_users_7d = await user_service.get_active_users_count(days=7)
        
        # Get memory statistics (this would come from a monitoring system)
        # For now, we'll make placeholder values
        total_memories = await memory_manager.get_total_memory_count()
        
        # Get interaction statistics
        total_interactions = await user_service.get_total_interaction_count()
        interactions_24h = await user_service.get_recent_interaction_count(hours=24)
        
        # Get system health
        # scheduler = await get_scheduler()
        # scheduler_status = "running" if scheduler and scheduler.scheduler.running else "stopped"
        
        return {
            "timestamp": datetime.utcnow(),
            "system_stats": {
                "total_users": total_users,
                "active_users_24h": active_users_24h,
                "active_users_7d": active_users_7d,
                "total_memories": total_memories,
                "total_interactions": total_interactions,
                "interactions_24h": interactions_24h,
                # "scheduler_status": scheduler_status
            }
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/security/incidents", response_model=List[Dict[str, Any]])
async def get_security_incidents(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    severity: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    status: Optional[str] = Query(None, regex="^(detected|investigating|resolved|ignored)$"),
    user_service: UserService = Depends(get_users)
):
    """
    Get security incidents with optional filtering.
    Shows detected threats, injection attempts, and other security events.
    """
    try:
        incidents = await user_service.get_security_incidents(
            limit=limit,
            offset=offset,
            severity=severity,
            status=status
        )
        
        return incidents
    except Exception as e:
        logger.error(f"Error getting security incidents: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cleanup", response_model=Dict[str, Any])
async def run_system_cleanup(
    cleanup_type: str = Query(..., regex="^(memories|users|logs|all)$"),
    user_service: UserService = Depends(get_users),
    memory_manager: MemoryManager = Depends(get_memory)
):
    """
    Run system cleanup operations.
    Options: 'memories' (old/deprecated memories), 'users' (inactive users), 'logs', or 'all'.
    """
    try:
        cleanup_results = {}
        
        if cleanup_type in ['memories', 'all']:
            # Clean up old memories
            cleaned_memories = await memory_manager.cleanup_old_memories()
            cleanup_results['memories_cleaned'] = cleaned_memories
        
        if cleanup_type in ['users', 'all']:
            # Clean up inactive users (this would be implemented based on retention policy)
            cleaned_users = await user_service.cleanup_inactive_users()
            cleanup_results['users_cleaned'] = cleaned_users
        
        if cleanup_type in ['logs', 'all']:
            # Clean up old logs (would be implemented with log management system)
            cleanup_results['logs_cleaned'] = "Not implemented in this example"
        
        logger.info(f"System cleanup completed: {cleanup_type}, results: {cleanup_results}")
        
        return {
            "cleanup_type": cleanup_type,
            "results": cleanup_results,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Error during system cleanup: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/maintenance/migrate_memories", response_model=Dict[str, int])
async def migrate_user_memories(
    source_user_id: str,
    target_user_id: str,
    user_service: UserService = Depends(get_users),
    memory_manager: MemoryManager = Depends(get_memory)
):
    """
    Migrate memories from one user to another.
    Useful for account merging or data migration scenarios.
    """
    try:
        # Verify both users exist
        source_user = await user_service.get_user_profile(source_user_id)
        target_user = await user_service.get_user_profile(target_user_id)
        
        if not source_user or not target_user:
            raise HTTPException(status_code=404, detail="Source or target user not found")
        
        # Migrate memories
        migrated_count = await memory_manager.migrate_memories(
            source_user_id=source_user_id,
            target_user_id=target_user_id
        )
        
        logger.info(f"Migrated {migrated_count} memories from {source_user_id} to {target_user_id}")
        
        return {
            "migrated_count": migrated_count,
            "source_user_id": source_user_id,
            "target_user_id": target_user_id,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Error migrating memories from {source_user_id} to {target_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/users/{user_id}/status", response_model=UserProfile)
async def update_user_status(
    user_id: str,
    status: str = Query(..., regex="^(active|inactive|suspended|deleted)$"),
    reason: Optional[str] = Query(None),
    user_service: UserService = Depends(get_users)
):
    """
    Update the status of a specific user.
    Admins can activate/deactivate/suspend users based on guidelines.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Update user status
        updated_user = await user_service.update_user_status(
            user_id=user_id,
            new_status=status,
            reason=reason
        )
        
        logger.info(f"Updated status for user {user_id} to {status}")
        
        return updated_user
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except Exception as e:
        logger.error(f"Error updating status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scheduler/status", response_model=Dict[str, Any])
async def get_scheduler_status():
    """
    Get the status of all scheduled background jobs.
    """
    try:
        # scheduler = await get_scheduler()
        # if not scheduler:
        #     raise HTTPException(status_code=500, detail="Scheduler not initialized")
        
        # jobs_status = scheduler.get_all_jobs_status()
        
        return {
            # "scheduler_running": scheduler.scheduler.running,
            # "job_count": len(jobs_status),
            # "jobs": jobs_status,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/scheduler/{job_id}/control", response_model=Dict[str, str])
async def control_scheduler_job(
    job_id: str,
    action: str = Query(..., regex="^(pause|resume|trigger)$"),
    user_service: UserService = Depends(get_users)
):
    """
    Control a specific scheduled job.
    Actions: pause, resume, or trigger immediately.
    """
    try:
        # scheduler = await get_scheduler()
        # if not scheduler:
        #     raise HTTPException(status_code=500, detail="Scheduler not initialized")
        
        # job = scheduler.scheduler.get_job(job_id)
        # if not job:
        #     raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # if action == "pause":
        #     await scheduler.pause_job(job_id)
        #     message = f"Job {job_id} paused"
        # elif action == "resume":
        #     await scheduler.resume_job(job_id)
        #     message = f"Job {job_id} resumed"
        # elif action == "trigger":
        #     # Trigger the job immediately
        #     job.func()
        #     message = f"Job {job_id} triggered immediately"
        # else:
        #     raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
        
        message = f"Action {action} on job {job_id} would be executed"
        
        logger.info(message)
        
        return {
            "message": message,
            "job_id": job_id,
            "action": action,
            "timestamp": datetime.utcnow()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling scheduler job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/background/tasks", response_model=Dict[str, Any])
async def get_background_tasks_status():
    """
    Get status of all background tasks and processes.
    """
    try:
        # bg_manager = await get_background_manager()
        # if not bg_manager:
        #     raise HTTPException(status_code=500, detail="Background manager not initialized")
        
        # stats = await bg_manager.get_stats()
        
        return {
            "status": "not_implemented",
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Error getting background tasks status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/personality/reset/{user_id}", response_model=PersonalitySnapshot)
async def reset_user_personality(
    user_id: str,
    user_service: UserService = Depends(get_users),
    personality_engine: PersonalityEngine = Depends(get_personality)
):
    """
    Reset a user's personality to default values.
    This is an admin function for troubleshooting or user requests.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Reset personality
        reset_snapshot = await personality_engine.reset_personality(user_id)
        
        logger.info(f"Personality reset for user {user_id}")
        
        return reset_snapshot
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except Exception as e:
        logger.error(f"Error resetting personality for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/debug/user/{user_id}", response_model=Dict[str, Any])
async def debug_user_data(
    user_id: str,
    include_memories: bool = Query(False),
    include_interactions: bool = Query(False),
    user_service: UserService = Depends(get_users),
    memory_manager: MemoryManager = Depends(get_memory)
):
    """
    Debug endpoint to get comprehensive user data for troubleshooting.
    Includes user profile, personality, and optionally memories and interactions.
    """
    try:
        # Get user profile
        user_profile = await user_service.get_user_profile(user_id)
        if not user_profile:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # For now, return a simplified debug response
        debug_data = {
            "user_profile": str(user_profile),
            "timestamp": datetime.utcnow()
        }
        
        return debug_data
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except Exception as e:
        logger.error(f"Error getting debug data for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")