from datetime import datetime, time, timedelta
import asyncio
from abc import ABC, abstractmethod

from app.service_base import BaseService

class ScheduledService(BaseService, ABC):
    service_name = "Scheduled Service"
    run_time: time = time(hour=3, minute=0)  # Standard: 03:00 Uhr

    async def run(self):
        self.logger.info(f"[{self.service_name}] Waiting to run at {self.run_time.strftime('%H:%M')} daily.")
        
        while True:
            now = datetime.now()
            today_run = datetime.combine(now.date(), self.run_time)

            # Wenn die geplante Zeit heute schon vorbei ist, plane für morgen
            if now >= today_run:
                next_run = today_run + timedelta(days=1)
            else:
                next_run = today_run

            sleep_seconds = (next_run - now).total_seconds()
            self.logger.info(f"[{self.service_name}] Next run in {int(sleep_seconds)} seconds.")
            await asyncio.sleep(sleep_seconds)

            try:
                self.logger.info(f"[{self.service_name}] Running scheduled task...")
                await self.run_scheduled_task()
            except Exception as e:
                self.logger.error(f"[{self.service_name}] Error during scheduled task: {e}")

    @abstractmethod
    async def run_scheduled_task(self):
        """Diese Methode wird täglich zur definierten Zeit aufgerufen."""
        raise NotImplementedError("Please implement `run_scheduled_task()` in your subclass.")
