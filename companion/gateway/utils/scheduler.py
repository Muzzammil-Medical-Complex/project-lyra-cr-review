"""
Background job scheduling utility for the AI Companion System.
Manages recurring tasks like nightly reflection, proactive checks, and needs decay.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional
import asyncio
import logging

from ..agents.proactive_manager import ProactiveManager
from ..agents.reflection import ReflectionAgent
from ..services.personality_engine import PersonalityEngine
from ..services.memory_manager import MemoryManager
from ..services.user_service import UserService
from ..services.groq_client import GroqClient
from ..database import DatabaseManager


class SchedulerService:
    """Manages APScheduler for background jobs in the AI Companion System."""
    
    def __init__(self, services_container):
        """
        Initialize the scheduler with service container
        """
        self.services = services_container
        self.scheduler = AsyncIOScheduler(timezone=ZoneInfo("UTC"))
        self.logger = logging.getLogger(__name__)
        
        # Job functions that will be scheduled
        self._job_functions = {}
    
    async def initialize_scheduler(self):
        """Initialize and start the scheduler with all required jobs."""
        # Add all background jobs
        await self._add_reflection_job()
        await self._add_proactive_check_job()
        await self._add_memory_maintenance_job()
        await self._add_needs_decay_job()
        await self._add_user_engagement_check_job()
        
        # Start the scheduler
        self.scheduler.start()
        self.logger.info("Scheduler initialized and started")
    
    async def _add_reflection_job(self):
        """Add the nightly reflection job."""
        # Nightly reflection runs at 3:00 AM server time
        self.scheduler.add_job(
            func=self._run_nightly_reflection,
            trigger=CronTrigger(hour=3, minute=0),
            id='nightly_reflection',
            name='Nightly personality reflection and memory consolidation',
            replace_existing=True,
            max_instances=1  # Prevent overlapping runs
        )
        self.logger.info("Added nightly reflection job")
    
    async def _add_proactive_check_job(self):
        """Add the proactive conversation check job."""
        # Check for proactive opportunities every 5 minutes
        self.scheduler.add_job(
            func=self._run_proactive_checks,
            trigger=IntervalTrigger(minutes=5),
            id='proactive_checks',
            name='Frequent proactive conversation checks',
            replace_existing=True,
            max_instances=2  # Allow some overlap for different users
        )
        self.logger.info("Added proactive checks job")
    
    async def _add_memory_maintenance_job(self):
        """Add memory maintenance and cleanup jobs."""
        # Update memory recency every 4 hours
        self.scheduler.add_job(
            func=self._update_memory_recency,
            trigger=CronTrigger(hour='*/4'),  # Every 4 hours
            id='memory_recency_update',
            name='Update memory recency scores',
            replace_existing=True
        )
        
        # Clean up old memories weekly
        self.scheduler.add_job(
            func=self._cleanup_old_memories,
            trigger=CronTrigger(day_of_week='sun', hour=2, minute=0),  # Sunday at 2 AM
            id='memory_cleanup',
            name='Clean up old memories',
            replace_existing=True
        )
        self.logger.info("Added memory maintenance jobs")
    
    async def _add_needs_decay_job(self):
        """Add psychological needs decay job."""
        # Decay user needs every hour
        self.scheduler.add_job(
            func=self._decay_psychological_needs,
            trigger=IntervalTrigger(hours=1),
            id='needs_decay',
            name='Decay psychological needs',
            replace_existing=True,
            max_instances=1
        )
        self.logger.info("Added needs decay job")
    
    async def _add_user_engagement_check_job(self):
        """Add user engagement health check job."""
        # Check for inactive users daily
        self.scheduler.add_job(
            func=self._check_user_engagement,
            trigger=CronTrigger(hour=1, minute=0),  # Daily at 1 AM
            id='user_engagement_check',
            name='Check user engagement and health',
            replace_existing=True
        )
        self.logger.info("Added user engagement check job")
    
    async def _run_nightly_reflection(self):
        """Wrapper function to run the nightly reflection process."""
        try:
            self.logger.info("Starting nightly reflection...")
            
            reflection_agent = ReflectionAgent(
                memory_manager=self.services.memory,
                personality_engine=self.services.personality,
                groq_client=self.services.groq,
                db_manager=self.services.db
            )
            
            report = await reflection_agent.run_nightly_reflection()
            self.logger.info(f"Nightly reflection completed. Processed {len(report.batch_results or [])} batches")
            
        except Exception as e:
            self.logger.exception("Error in nightly reflection")
            # Log error to database as well
            try:
                await self.services.db.log_background_job_error("nightly_reflection", str(e))
            except Exception:
                pass  # Don't let logging error break the job
    
    async def _run_proactive_checks(self):
        """Check for proactive conversation opportunities."""
        try:
            self.logger.info("Starting proactive checks...")
            
            proactive_manager = ProactiveManager(
                personality_engine=self.services.personality,
                memory_manager=self.services.memory,
                user_service=self.services.users,
                groq_client=self.services.groq,
                db_manager=self.services.db
            )
            
            # Get all active users to check
            active_users = await self.services.db.get_active_users_for_proactive_check()
            
            initiated_count = 0
            # Track last proactive message time per user
            cooldown_hours = 4  # Minimum hours between proactive messages
            
            for user_id in active_users:
                try:
                    # Check if user was recently sent a proactive message
                    last_proactive = await self.services.db.get_last_proactive_message_time(user_id)
                    now = datetime.now(timezone.utc)
                    if last_proactive:
                        if last_proactive.tzinfo is None:
                            last_proactive = last_proactive.replace(tzinfo=timezone.utc)
                        else:
                            last_proactive = last_proactive.astimezone(timezone.utc)
                        if (now - last_proactive).total_seconds() < cooldown_hours * 3600:
                            continue
                    
                    if await proactive_manager.should_initiate_conversation(user_id):
                        # Generate and send proactive message
                        score = await proactive_manager.calculate_proactive_score(user_id)
                        starter = await proactive_manager.generate_conversation_starter(
                            user_id, score.trigger_reason
                        )
                        
                        # Send the proactive message via the appropriate channel
                        await self._send_proactive_message(user_id, starter, score.trigger_reason)
                        initiated_count += 1
                        
                        # Log the proactive conversation
                        await self.services.db.log_proactive_conversation(
                            user_id, starter, score.trigger_reason, score.total_score
                        )
                        
                        # Small delay to avoid overwhelming the system
                        await asyncio.sleep(0.1)
                        
                except Exception as e:
                    self.logger.exception(f"Error checking proactive for user {user_id}: {e}")
                    continue
            
            self.logger.info(f"Proactive checks completed. Initiated {initiated_count} conversations")
            
        except Exception as e:
            self.logger.exception(f"Error in proactive checks: {e}")
            try:
                await self.services.db.log_background_job_error("proactive_checks", str(e))
            except Exception:
                pass
    
    async def _update_memory_recency(self):
        """Update recency scores for all memories."""
        try:
            self.logger.info("Starting memory recency update...")
            
            # This is a simplified implementation
            # In a real system, this would update the recency scores in the memory system
            await self.services.memory.apply_recency_decay_all_users()
            self.logger.info("Memory recency update completed")
            
        except Exception as e:
            self.logger.exception(f"Error in memory recency update: {e}")
            try:
                await self.services.db.log_background_job_error("memory_recency_update", str(e))
            except Exception:
                pass
    
    async def _cleanup_old_memories(self):
        """Clean up old or obsolete memories."""
        try:
            self.logger.info("Starting memory cleanup...")
            
            # This would implement cleanup logic based on importance, recency, and other factors
            cleaned_count = await self.services.memory.cleanup_old_memories()
            self.logger.info(f"Memory cleanup completed. Cleaned {cleaned_count} memories")
            
        except Exception as e:
            self.logger.exception(f"Error in memory cleanup: {e}")
            try:
                await self.services.db.log_background_job_error("memory_cleanup", str(e))
            except Exception:
                pass
    
    async def _decay_psychological_needs(self):
        """Apply decay to all users' psychological needs."""
        try:
            self.logger.info("Starting needs decay...")
            
            # Get all active users
            active_users = await self.services.db.get_all_active_users()

            decayed_count = 0
            for user_id in active_users:
                try:
                    # Use personality engine which returns PsychologicalNeed models
                    needs = await self.services.personality.get_user_needs(user_id)

                    for need in needs:
                        # Apply decay rate based on time elapsed
                        hours_since_update = 1  # Assuming hourly job
                        decay_amount = need.decay_rate * hours_since_update
                        # Apply decay as a negative delta via personality engine
                        await self.services.personality.update_need_level(
                            user_id, need.need_type, -decay_amount
                        )
                        decayed_count += 1
                        
                except Exception as e:
                    self.logger.exception(f"Error decaying needs for user {user_id}: {e}")
                    continue
            
            self.logger.info(f"Needs decay completed. Updated {decayed_count} needs")
            
        except Exception as e:
            self.logger.exception(f"Error in needs decay: {e}")
            try:
                await self.services.db.log_background_job_error("needs_decay", str(e))
            except Exception:
                pass
    
    async def _check_user_engagement(self):
        """Check user engagement and system health."""
        try:
            self.logger.info("Starting user engagement check...")
            
            # Get engagement metrics
            metrics = await self.services.db.get_user_engagement_metrics()
            
            # Log metrics for monitoring
            self.logger.info(f"User engagement metrics: {metrics}")
            
            # Check for system health issues
            health_status = await self._check_system_health()
            if not health_status['healthy']:
                self.logger.warning(f"System health issues detected: {health_status['issues']}")
                
            self.logger.info("User engagement check completed")
            
        except Exception as e:
            self.logger.exception(f"Error in user engagement check: {e}")
            try:
                await self.services.db.log_background_job_error("user_engagement_check", str(e))
            except Exception:
                pass
    
    async def _check_system_health(self) -> dict:
        """Check health of various system components."""
        health = {
            'healthy': True,
            'issues': [],
            'components': {}
        }
        
        # Check database connectivity
        try:
            db_ok = await self.services.db.health_check()
            if db_ok:
                health['components']['database'] = 'healthy'
            else:
                health['components']['database'] = 'unhealthy'
                health['healthy'] = False
                health['issues'].append("Database health check reported unavailable")
        except Exception as e:
            health['healthy'] = False
            health['issues'].append(f"Database health check failed: {e}")
            health['components']['database'] = 'unhealthy'
        
        # Check if other services are accessible
        try:
            # Check if memory manager is responsive
            test_result = await self.services.memory.health_check()
            health['components']['memory_manager'] = 'healthy' if test_result else 'unhealthy'
            if not test_result:
                health['healthy'] = False
                health['issues'].append("Memory manager health check failed")
        except Exception as e:
            health['healthy'] = False
            health['issues'].append(f"Memory manager health check failed: {e}")
            health['components']['memory_manager'] = 'unhealthy'
        
        return health
    
    async def _send_proactive_message(self, user_id: str, message: str, trigger_reason: str):
        """Send a proactive message to a user through the appropriate channel."""
        try:
            # In a real implementation, this would send the message through Discord or other channels
            # For now, we'll log it and assume a service handles the actual sending
            self.logger.info(
                f"Sending proactive message to {user_id}: {message[:50]}... (reason: {trigger_reason})"
            )
            
            # Example implementation would call discord_sender or similar service
            # await self.services.discord_sender.send_proactive_message(user_id, message)
            
            # Update user's proactive message stats
            await self.services.db.increment_proactive_message_count(user_id)
            
        except Exception as e:
            self.logger.exception(f"Error sending proactive message to {user_id}: {e}")
            try:
                await self.services.db.log_proactive_message_error(user_id, message, str(e))
            except Exception:
                pass
    
    def get_job_status(self, job_id: str) -> dict:
        """Get the status of a specific job."""
        job = self.scheduler.get_job(job_id)
        if not job:
            return {'exists': False}
        
        return {
            'exists': True,
            'id': job.id,
            'name': job.name,
            'next_run_time': job.next_run_time,
            'trigger': str(job.trigger)
        }
    
    def get_all_jobs_status(self) -> dict:
        """Get the status of all scheduled jobs."""
        jobs = self.scheduler.get_jobs()
        status = {}
        
        for job in jobs:
            status[job.id] = {
                'name': job.name,
                'next_run_time': job.next_run_time,
                'trigger': str(job.trigger)
            }
        
        return status
    
    def shutdown_scheduler(self):
        """Clean shutdown of the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            self.logger.info("Scheduler shut down successfully")
    
    async def pause_job(self, job_id: str):
        """Pause a specific job."""
        job = self.scheduler.get_job(job_id)
        if job:
            job.pause()
            self.logger.info(f"Paused job: {job_id}")
    
    async def resume_job(self, job_id: str):
        """Resume a paused job."""
        job = self.scheduler.get_job(job_id)
        if job:
            job.resume()
            self.logger.info(f"Resumed job: {job_id}")
    
    async def add_custom_job(self, func, trigger, job_id: str, name: Optional[str] = None, **kwargs):
        """Add a custom job to the scheduler."""
        self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            name=name or job_id,
            **kwargs
        )
        self.logger.info(f"Added custom job: {job_id}")
    
    async def remove_job(self, job_id: str):
        """Remove a job from the scheduler."""
        job = self.scheduler.get_job(job_id)
        if job:
            job.remove()
            self.logger.info(f"Removed job: {job_id}")


# Global scheduler instance (this would typically be managed by the main application)
scheduler_service = None


async def setup_background_jobs(services_container) -> SchedulerService:
    """Setup function to initialize the scheduler with all required jobs."""
    global scheduler_service
    
    scheduler_service = SchedulerService(services_container)
    await scheduler_service.initialize_scheduler()
    
    return scheduler_service


async def get_scheduler() -> SchedulerService:
    """Get the global scheduler instance."""
    global scheduler_service
    return scheduler_service