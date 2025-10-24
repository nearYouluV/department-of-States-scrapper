#!/usr/bin/env python3
"""
Wrapper script to run the scraper continuously with proper monitoring and restart logic.
"""

import asyncio
import signal
import sys
import time
import traceback
from datetime import datetime, timezone, date
from pathlib import Path
import subprocess
import os
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/runner.log', mode='a')
    ]
)
logger = logging.getLogger('scraper_runner')

class ScraperRunner:
    def __init__(self):
        self.should_stop = False
        self.current_process = None
        self.last_run_date = None
        self.consecutive_failures = 0
        
        # Configuration from environment variables
        self.max_consecutive_failures = int(os.getenv('SCRAPER_MAX_FAILURES', '3'))
        self.auto_restart = os.getenv('SCRAPER_AUTO_RESTART', 'true').lower() == 'true'
        self.restart_on_failure = os.getenv('SCRAPER_RESTART_ON_FAILURE', 'true').lower() == 'true'
        self.daily_restart = os.getenv('SCRAPER_DAILY_RESTART', 'true').lower() == 'true'
        self.log_activity_timeout = int(os.getenv('LOG_ACTIVITY_TIMEOUT', '1800'))  # 30 minutes
        
        # Ensure logs directory exists
        Path('/app/logs').mkdir(parents=True, exist_ok=True)
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        logger.info(f"Scraper runner initialized with config:")
        logger.info(f"  - Auto restart: {self.auto_restart}")
        logger.info(f"  - Restart on failure: {self.restart_on_failure}")
        logger.info(f"  - Daily restart: {self.daily_restart}")
        logger.info(f"  - Max consecutive failures: {self.max_consecutive_failures}")
        logger.info(f"  - Log activity timeout: {self.log_activity_timeout}s")
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.should_stop = True
        if self.current_process:
            logger.info("Terminating current scraper process...")
            self.current_process.terminate()
    
    def _check_memory_usage(self) -> bool:
        """Check if memory usage is within acceptable limits"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            max_memory_mb = int(os.getenv('SCRAPER_MAX_MEMORY_MB', '2048'))
            
            if memory_mb > max_memory_mb:
                logger.warning(f"Memory usage too high: {memory_mb:.1f}MB > {max_memory_mb}MB")
                return False
            
            logger.debug(f"Memory usage: {memory_mb:.1f}MB")
            return True
            
        except ImportError:
            # psutil not available, skip memory check
            return True
        except Exception as e:
            logger.warning(f"Could not check memory usage: {e}")
            return True
    
    def _should_run_today(self) -> bool:
        """Check if scraper should run today"""
        current_date = date.today()
        
        # Always run if we haven't run today
        if self.last_run_date != current_date:
            return True
            
        # Check if there's a completion marker for today
        completion_file = f"/tmp/scraper_completed_{current_date}"
        return not os.path.exists(completion_file)
    
    def _mark_completion(self):
        """Mark that scraper completed successfully today"""
        current_date = date.today()
        completion_file = f"/tmp/scraper_completed_{current_date}"
        
        # Update last run tracking
        with open("/tmp/last_scraper_run", "w") as f:
            f.write(str(current_date))
        
        # Create completion marker
        with open(completion_file, "w") as f:
            f.write(str(datetime.now(timezone.utc)))
        
        self.last_run_date = current_date
        self.consecutive_failures = 0
        logger.info(f"Marked scraper completion for {current_date}")
    
    def _cleanup_old_markers(self):
        """Remove old completion markers"""
        current_date = date.today()
        for file_path in Path("/tmp").glob("scraper_completed_*"):
            try:
                file_date_str = file_path.name.replace("scraper_completed_", "")
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
                if file_date < current_date:
                    file_path.unlink()
                    logger.info(f"Cleaned up old completion marker: {file_path}")
            except (ValueError, OSError) as e:
                logger.warning(f"Could not process file {file_path}: {e}")
    
    async def _run_scraper(self) -> bool:
        """Run the scraper process and monitor it"""
        logger.info("Starting scraper process...")
        
        try:
            # Start the scraper process
            self.current_process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "scraper.new_york_scrapper",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd="/app"
            )
            
            # Monitor the process
            stdout, stderr = await self.current_process.communicate()
            
            if self.current_process.returncode == 0:
                logger.info("Scraper completed successfully")
                logger.info(f"Stdout: {stdout.decode()}")
                self._mark_completion()
                return True
            else:
                logger.error(f"Scraper failed with return code: {self.current_process.returncode}")
                logger.error(f"Stderr: {stderr.decode()}")
                self.consecutive_failures += 1
                return False
                
        except Exception as e:
            logger.error(f"Error running scraper: {e}")
            logger.error(traceback.format_exc())
            self.consecutive_failures += 1
            return False
        finally:
            self.current_process = None
    
    def _calculate_wait_time(self) -> int:
        """Calculate how long to wait before next run"""
        if self.consecutive_failures == 0:
            # Successful run - wait until next day
            return 3600  # Check every hour if it's a new day
        elif self.consecutive_failures <= 2:
            # Few failures - wait 10 minutes
            return 600
        else:
            # Many failures - wait 30 minutes
            return 1800
    
    async def run(self):
        """Main runner loop"""
        logger.info("Scraper runner starting...")
        
        # Clean up old markers on startup
        self._cleanup_old_markers()
        
        while not self.should_stop:
            try:
                # Check memory usage periodically
                if not self._check_memory_usage():
                    logger.warning("Memory usage too high, requesting restart...")
                    if self.auto_restart:
                        break  # Exit loop to restart container
                
                if self._should_run_today():
                    if self.consecutive_failures >= self.max_consecutive_failures:
                        if not self.restart_on_failure:
                            logger.error(
                                f"Too many consecutive failures ({self.consecutive_failures}). "
                                "Auto-restart disabled, stopping."
                            )
                            break
                        
                        logger.warning(
                            f"Too many consecutive failures ({self.consecutive_failures}). "
                            "Waiting longer before retry..."
                        )
                        await asyncio.sleep(3600)  # Wait 1 hour
                        self.consecutive_failures = 0  # Reset after long wait
                        continue
                    
                    logger.info("Running scraper for today...")
                    success = await self._run_scraper()
                    
                    if not success and self.should_stop:
                        logger.info("Scraper interrupted by shutdown signal")
                        break
                        
                else:
                    logger.info("Scraper already completed for today")
                    self.consecutive_failures = 0
                
                # Wait before next check
                wait_time = self._calculate_wait_time()
                logger.info(f"Waiting {wait_time} seconds before next check...")
                
                # Wait with periodic checks for shutdown signal
                for _ in range(wait_time // 10):
                    if self.should_stop:
                        break
                    await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Unexpected error in runner loop: {e}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(60)  # Wait 1 minute on unexpected errors
        
        logger.info("Scraper runner shutting down...")

async def main():
    """Entry point"""
    runner = ScraperRunner()
    await runner.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
