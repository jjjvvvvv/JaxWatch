#!/usr/bin/env python3
"""
DEPRECATED (non-MVP): Adaptive Polling

Moved to experiments/advanced. Importing this module without explicitly enabling
advanced features will raise.
"""

import os as _os

if _os.getenv("JAXWATCH_ADVANCED", "0").lower() in {"1", "true", "yes", "on"}:
    from experiments.advanced.adaptive_polling import *  # noqa: F401,F403
else:
    raise ImportError(
        "Adaptive polling is non-MVP and has moved to experiments/advanced. "
        "Set JAXWATCH_ADVANCED=1 or import experiments.advanced.adaptive_polling."
    )

    def calculate_next_poll_time(self, schedule: PollingSchedule) -> datetime:
        """Calculate when to next poll this source"""

        now = datetime.now()

        # Start with basic frequency calculation
        if schedule.frequency == PollingFrequency.DAILY:
            base_next = now + timedelta(days=1)
        elif schedule.frequency == PollingFrequency.WEEKLY:
            base_next = now + timedelta(weeks=1)
        elif schedule.frequency == PollingFrequency.BIWEEKLY:
            base_next = now + timedelta(weeks=2)
        elif schedule.frequency == PollingFrequency.MONTHLY:
            base_next = now + timedelta(days=30)
        else:  # ON_DEMAND
            return now + timedelta(days=365)  # Far future

        # Apply preferred time
        next_poll = base_next.replace(
            hour=schedule.preferred_time.hour,
            minute=schedule.preferred_time.minute,
            second=0,
            microsecond=0
        )

        # For sources with meeting days, align to those days
        if schedule.meeting_days:
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                        "Friday", "Saturday", "Sunday"]

            target_weekdays = [day_names.index(day) for day in schedule.meeting_days]

            # Find next occurrence of a meeting day
            days_ahead = 7  # Start with a week out
            while True:
                candidate = now + timedelta(days=days_ahead)
                if candidate.weekday() in target_weekdays:
                    # Apply any day offset (e.g., check day after meeting)
                    offset = schedule.custom_patterns.get("agenda_day_offset", 0)
                    next_poll = candidate + timedelta(days=offset)
                    next_poll = next_poll.replace(
                        hour=schedule.preferred_time.hour,
                        minute=schedule.preferred_time.minute,
                        second=0,
                        microsecond=0
                    )
                    break
                days_ahead += 1
                if days_ahead > 14:  # Safety valve
                    break

        # Skip holidays
        while self.is_holiday(next_poll):
            next_poll += timedelta(days=1)

        # Apply exponential backoff for consecutive failures
        if schedule.consecutive_failures > 0:
            backoff_hours = min(24, 2 ** schedule.consecutive_failures)
            next_poll += timedelta(hours=backoff_hours)
            self.logger.info(f"Applied {backoff_hours}h backoff for {schedule.source_name} "
                           f"({schedule.consecutive_failures} consecutive failures)")

        return next_poll

    def should_poll_now(self, source_name: str) -> bool:
        """Check if a source should be polled now"""

        if source_name not in self.schedules:
            self.logger.warning(f"No schedule found for source: {source_name}")
            return False

        schedule = self.schedules[source_name]

        # Check if source is active
        if schedule.status != SourceStatus.ACTIVE:
            return False

        # Check if it's a holiday
        if self.is_holiday(datetime.now()):
            return False

        # Check if next scheduled time has passed
        if schedule.next_scheduled is None:
            # First time, calculate schedule
            schedule.next_scheduled = self.calculate_next_poll_time(schedule)
            self._save_config()
            return True

        return datetime.now() >= schedule.next_scheduled

    def record_poll_attempt(self, source_name: str, success: bool, error_msg: str = None):
        """Record the result of a polling attempt"""

        if source_name not in self.schedules:
            return

        schedule = self.schedules[source_name]
        now = datetime.now()

        schedule.last_attempt = now
        schedule.retry_count += 1

        if success:
            schedule.last_success = now
            schedule.consecutive_failures = 0
            schedule.status = SourceStatus.ACTIVE
            schedule.retry_count = 0

            # Schedule next poll
            schedule.next_scheduled = self.calculate_next_poll_time(schedule)

            self.logger.info(f"Successful poll of {source_name}, next scheduled: {schedule.next_scheduled}")

        else:
            schedule.consecutive_failures += 1

            if schedule.consecutive_failures >= schedule.max_retries:
                schedule.status = SourceStatus.ERROR
                self.logger.error(f"Source {source_name} marked as ERROR after {schedule.consecutive_failures} failures")
            else:
                # Schedule retry with backoff
                schedule.next_scheduled = self.calculate_next_poll_time(schedule)
                self.logger.warning(f"Poll failed for {source_name}, retry scheduled: {schedule.next_scheduled}")

            if error_msg:
                self.logger.error(f"Poll error for {source_name}: {error_msg}")

        # Save updated configuration
        self._save_config()

    def get_polling_status(self) -> Dict[str, Any]:
        """Get current status of all polling schedules"""

        status = {
            "last_updated": datetime.now().isoformat(),
            "sources": {}
        }

        for source_name, schedule in self.schedules.items():
            # Handle both enum and string values
            status_val = schedule.status.value if hasattr(schedule.status, 'value') else schedule.status
            freq_val = schedule.frequency.value if hasattr(schedule.frequency, 'value') else schedule.frequency

            status["sources"][source_name] = {
                "status": status_val,
                "frequency": freq_val,
                "last_success": schedule.last_success.isoformat() if schedule.last_success else None,
                "next_scheduled": schedule.next_scheduled.isoformat() if schedule.next_scheduled else None,
                "consecutive_failures": schedule.consecutive_failures,
                "should_poll_now": self.should_poll_now(source_name)
            }

        return status

    def update_schedule(self, source_name: str, **kwargs):
        """Update a polling schedule"""

        if source_name not in self.schedules:
            self.logger.error(f"Cannot update unknown source: {source_name}")
            return

        schedule = self.schedules[source_name]

        # Update allowed fields
        for field, value in kwargs.items():
            if hasattr(schedule, field):
                setattr(schedule, field, value)
                self.logger.info(f"Updated {source_name}.{field} = {value}")

        # Recalculate next poll time if frequency changed
        if 'frequency' in kwargs or 'preferred_time' in kwargs:
            schedule.next_scheduled = self.calculate_next_poll_time(schedule)

        self._save_config()

    def force_poll(self, source_name: str):
        """Force immediate polling of a source"""

        if source_name not in self.schedules:
            self.logger.error(f"Cannot force poll unknown source: {source_name}")
            return

        schedule = self.schedules[source_name]
        schedule.next_scheduled = datetime.now()
        schedule.status = SourceStatus.ACTIVE
        self._save_config()

        self.logger.info(f"Forced immediate poll for {source_name}")

# Convenience functions for integration with existing observatory
def create_default_poller() -> AdaptivePoller:
    """Create poller with Jacksonville-specific defaults"""
    return AdaptivePoller()

def should_poll_source(source_name: str, poller: AdaptivePoller = None) -> bool:
    """Check if a source should be polled (convenience function)"""
    if poller is None:
        poller = create_default_poller()
    return poller.should_poll_now(source_name)

def record_poll_result(source_name: str, success: bool, error_msg: str = None,
                      poller: AdaptivePoller = None):
    """Record polling result (convenience function)"""
    if poller is None:
        poller = create_default_poller()
    poller.record_poll_attempt(source_name, success, error_msg)

if __name__ == "__main__":
    # Example usage and testing
    poller = create_default_poller()

    print("🔄 Adaptive Polling System Status")
    status = poller.get_polling_status()

    for source_name, source_status in status["sources"].items():
        print(f"\n📊 {source_name}:")
        print(f"  Status: {source_status['status']}")
        print(f"  Frequency: {source_status['frequency']}")
        print(f"  Last Success: {source_status['last_success']}")
        print(f"  Next Scheduled: {source_status['next_scheduled']}")
        print(f"  Should Poll Now: {source_status['should_poll_now']}")
        print(f"  Consecutive Failures: {source_status['consecutive_failures']}")
