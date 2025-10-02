"""
Background task management utility for the AI Companion System.
Handles orchestration of long-running processes, graceful shutdown, and health monitoring.
"""
import asyncio
import logging
import signal
import sys
import time
import threading
from typing import List, Dict, Callable, Any, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from .scheduler import SchedulerService, get_scheduler
from ..database import DatabaseManager
from ..services.groq_client import GroqClient


class BackgroundTaskManager:
    """Manages background tasks, long-running processes, and graceful shutdown."""
    
    def __init__(self, db_manager: DatabaseManager, groq_client: GroqClient):
        self.db = db_manager
        self.groq = groq_client
        self.logger = logging.getLogger(__name__)
        
        # Track running tasks
        self.running_tasks: List[asyncio.Task] = []
        self.background_processes: Dict[str, Any] = {}
        self.shutdown_requested = False
        self.health_checks: Dict[str, Callable] = {}
        self.signal_handlers_initialized = False

        # Attempt to setup signal handlers if in main thread
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """
        Setup signal handlers for graceful shutdown.
        Only works when called from the main thread.
        """
        # Check if we're in the main thread
        if threading.current_thread() is not threading.main_thread():
            self.logger.warning(
                "Signal handlers cannot be registered from non-main thread. "
                "Call initialize_signal_handlers() from the main thread if needed."
            )
            return

        # Check platform support
        if sys.platform == 'win32':
            self.logger.debug("Windows platform detected, skipping SIGTERM handler (not supported)")
            # Only register SIGINT on Windows
            try:
                signal.signal(signal.SIGINT, self._signal_handler)
                self.signal_handlers_initialized = True
                self.logger.info("Signal handler registered for SIGINT")
            except ValueError as e:
                self.logger.warning(f"Failed to register signal handler: {e}")
        else:
            # Unix-like systems support both SIGTERM and SIGINT
            try:
                signal.signal(signal.SIGTERM, self._signal_handler)
                signal.signal(signal.SIGINT, self._signal_handler)
                self.signal_handlers_initialized = True
                self.logger.info("Signal handlers registered for SIGTERM and SIGINT")
            except ValueError as e:
                self.logger.warning(f"Failed to register signal handlers: {e}")

    def initialize_signal_handlers(self):
        """
        Explicitly initialize signal handlers from the main thread.

        This method should be called from the main thread to ensure signal
        handlers are properly registered. If called from a non-main thread,
        it will log a warning and return without registering handlers.

        Example:
            manager = BackgroundTaskManager(db, groq)
            manager.initialize_signal_handlers()  # Call from main thread
        """
        if self.signal_handlers_initialized:
            self.logger.debug("Signal handlers already initialized")
            return

        self._setup_signal_handlers()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.request_shutdown()

    def request_shutdown(self):
        """Request graceful shutdown of all background tasks."""
        self.logger.info("Shutdown requested")
        self.shutdown_requested = True

    async def register_health_check(self, name: str, check_func: Callable):
        """Register a health check function."""
        self.health_checks[name] = check_func

    async def run_health_checks(self) -> Dict[str, bool]:
        """Run all registered health checks."""
        results = {}
        
        for name, check_func in self.health_checks.items():
            try:
                result = await check_func() if asyncio.iscoroutinefunction(check_func) else check_func()
                results[name] = bool(result)
            except Exception as e:
                self.logger.error(f"Health check {name} failed: {e}")
                results[name] = False
        
        return results

    async def start_background_services(self, services_container):
        """Start all background services and processes."""
        self.logger.info("Starting background services...")
        
        # Start the scheduler
        try:
            scheduler_service = await get_scheduler()
            if scheduler_service is None:
                from .scheduler import setup_background_jobs
                scheduler_service = await setup_background_jobs(services_container)
            
            self.background_processes['scheduler'] = scheduler_service
            self.logger.info("Scheduler service started")
        except Exception as e:
            self.logger.error(f"Failed to start scheduler service: {e}")
            raise

        # Start any other background processes here
        # For example: monitoring, logging aggregation, etc.

        # Register health checks
        await self.register_health_check('scheduler', self._check_scheduler_health)
        await self.register_health_check('database', self._check_database_health)

    async def _check_scheduler_health(self) -> bool:
        """Check if the scheduler is running properly."""
        try:
            scheduler = await get_scheduler()
            if not scheduler or not scheduler.scheduler.running:
                return False
            
            # Check if jobs are running
            jobs = scheduler.get_all_jobs_status()
            return len(jobs) > 0
        except Exception as e:
            self.logger.debug(f"Scheduler health check failed: {e}")
            return False

    async def _check_database_health(self) -> bool:
        """Check if the database is accessible."""
        try:
            await self.db.health_check()
            return True
        except Exception as e:
            self.logger.debug(f"Database health check failed: {e}")
            return False

    async def monitor_system_health(self, check_interval: int = 30):
        """Monitor system health and report issues."""
        while not self.shutdown_requested:
            try:
                health_status = await self.run_health_checks()
                
                # Log health status
                unhealthy_services = [name for name, healthy in health_status.items() if not healthy]
                if unhealthy_services:
                    self.logger.warning(f"Unhealthy services detected: {unhealthy_services}")
                    
                    # Log to database for monitoring
                    await self.db.log_system_health_issue("unhealthy_services", str(unhealthy_services))
                else:
                    self.logger.debug("All services healthy")
                
                # Wait before next check
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in system health monitoring: {e}")
                await asyncio.sleep(check_interval)

    async def start_monitoring_tasks(self):
        """Start background monitoring tasks."""
        # Start health monitoring
        health_task = asyncio.create_task(self.monitor_system_health())
        self.running_tasks.append(health_task)

    async def execute_background_task(self, task_func: Callable, *args, **kwargs) -> asyncio.Task:
        """Execute a function as a background task."""
        async def wrapper():
            try:
                return await task_func(*args, **kwargs)
            except asyncio.CancelledError:
                self.logger.info(f"Background task {task_func.__name__} was cancelled")
                raise
            except Exception as e:
                self.logger.error(f"Background task {task_func.__name__} failed: {e}")
                raise
        
        task = asyncio.create_task(wrapper())
        self.running_tasks.append(task)
        
        # Remove completed tasks from tracking
        task.add_done_callback(lambda t: self.running_tasks.remove(t) if t in self.running_tasks else None)
        
        return task

    async def wait_for_all_tasks(self, timeout: Optional[float] = None):
        """Wait for all running tasks to complete."""
        if not self.running_tasks:
            return
        
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.running_tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout waiting for tasks to complete after {timeout} seconds")
            # Cancel remaining tasks
            for task in self.running_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait a bit more for tasks to handle cancellation
            await asyncio.gather(*self.running_tasks, return_exceptions=True)

    async def graceful_shutdown(self, timeout: float = 30.0):
        """Perform graceful shutdown of all background tasks."""
        self.logger.info("Starting graceful shutdown...")
        
        start_time = time.time()
        
        # Request shutdown to all background processes
        self.request_shutdown()
        
        # Cancel all running tasks
        for task in self.running_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.running_tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Tasks didn't complete within {timeout}s timeout, forcing shutdown")
            # Force cancel any remaining tasks
            for task in self.running_tasks:
                if not task.done():
                    task.cancel()
            # Give a final moment for cancellation to propagate
            await asyncio.sleep(0.1)
        
        # Shutdown scheduler
        try:
            scheduler = await get_scheduler()
            if scheduler:
                scheduler.shutdown_scheduler()
                self.logger.info("Scheduler shut down")
        except Exception as e:
            self.logger.error(f"Error shutting down scheduler: {e}")
        
        # Additional cleanup can go here
        self.logger.info("Background task manager shutdown completed")

from datetime import datetime, timezone

     async def health_check(self) -> Dict[str, Any]:
         """Perform a comprehensive health check of background services."""
         health_info = {
            'timestamp': datetime.now(timezone.utc),
             'running_tasks_count': len(self.running_tasks),
             'background_processes_count': len(self.background_processes),
             'shutdown_requested': self.shutdown_requested,
             'individual_checks': await self.run_health_checks()
         }
         
         return health_info

    async def get_task_stats(self) -> Dict[str, Any]:
        """Get statistics about running background tasks."""
        stats = {
            'total_tasks': len(self.running_tasks),
            'completed_tasks': 0,
            'running_tasks': 0,
            'cancelled_tasks': 0,
            'failed_tasks': 0,
            'task_names': []
        }
        
        for task in self.running_tasks:
            if task.done():
                stats['completed_tasks'] += 1
                if task.cancelled():
                    stats['cancelled_tasks'] += 1
                elif task.exception() is not None:
                    stats['failed_tasks'] += 1
            else:
                stats['running_tasks'] += 1
                
            # Record task name if available
            # Record task name if available
            try:
                stats['task_names'].append(task._coro.__name__)
            except (AttributeError, Exception):
                stats['task_names'].append('unknown')
            else:
                stats['task_names'].append('unknown')
        
        return stats

    async def restart_failed_tasks(self):
        """Restart any failed background tasks."""
        failed_tasks = [task for task in self.running_tasks if task.done() and task.exception() is not None]
        
        for task in failed_tasks:
            self.logger.warning(f"Restarting failed task: {task}")
            try:
                # Remove from tracking
                self.running_tasks.remove(task)
                
                # Here you would recreate the task based on its original function
                # This requires keeping track of task creation info
                # For now, we'll just log the restart attempt
                self.logger.info(f"Task restart logic would go here")
            except Exception as e:
                self.logger.error(f"Error restarting task: {e}")

    async def cleanup_resources(self):
        """Clean up any background resources."""
        # Cancel all remaining tasks
        for task in self.running_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to finish cancellation
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
        
        # Clear task list
        self.running_tasks.clear()


class BackgroundServiceManager:
    """Higher-level manager for background services."""

    def __init__(self, services_container):
        self.services = services_container
        self.logger = logging.getLogger(__name__)
        self.background_manager = BackgroundTaskManager(
            db_manager=services_container.db,
            groq_client=services_container.groq
        )
        self.initialized = False

    async def initialize(self):
        """Initialize the background service manager."""
        if self.initialized:
            return
            
        # Start background services
        await self.background_manager.start_background_services(self.services)
        
        # Start monitoring tasks
        await self.background_manager.start_monitoring_tasks()

        self.initialized = True
        self.logger.info("Background service manager initialized")

    async def start(self):
        """Start the background service manager."""
        if not self.initialized:
            await self.initialize()

        self.logger.info("Background service manager started")

    async def stop(self, timeout: float = 30.0):
        """Stop the background service manager."""
        await self.background_manager.graceful_shutdown(timeout)
        await self.background_manager.cleanup_resources()
        self.logger.info("Background service manager stopped")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on background services."""
        return await self.background_manager.health_check()

    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about background services."""
        return {
            'service_manager': 'running' if self.initialized else 'not_initialized',
            'task_stats': await self.background_manager.get_task_stats(),
            'health': await self.health_check()
        }


# Global background service manager instance
background_service_manager = None


async def initialize_background_services(services_container):
    """Initialize and start the background service manager."""
    global background_service_manager
    
    if background_service_manager is None:
        background_service_manager = BackgroundServiceManager(services_container)
        await background_service_manager.initialize()
        await background_service_manager.start()
    
    return background_service_manager


async def get_background_manager() -> BackgroundServiceManager:
    """Get the global background service manager instance."""
    global background_service_manager
    return background_service_manager


@asynccontextmanager
async def background_service_lifespan(services_container):
    """Lifespan manager for background services."""
    manager = await initialize_background_services(services_container)
    try:
        yield manager
    finally:
        if manager:
            await manager.stop()