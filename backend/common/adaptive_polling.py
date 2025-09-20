#!/usr/bin/env python3
"""
JaxWatch Adaptive Polling System
Department-specific scheduling with holiday awareness and exponential backoff
Principles: Simple, reliable, respectful of city resources
"""

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import json
from enum import Enum

logger = logging.getLogger(__name__)

class PollingFrequency(str, Enum):
    """Polling frequency options"""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    ON_DEMAND = "on_demand"

class SourceStatus(str, Enum):
    """Current status of a data source"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"

@dataclass
class PollingSchedule:
    """Department-specific polling configuration"""
    source_name: str
    frequency: PollingFrequency
    preferred_time: time = time(6, 0)  # 6 AM default
    retry_count: int = 0
    max_retries: int = 3
    last_attempt: Optional[datetime] = None
    last_success: Optional[datetime] = None
    next_scheduled: Optional[datetime] = None
    status: SourceStatus = SourceStatus.ACTIVE
    consecutive_failures: int = 0

    # Department-specific settings
    meeting_days: List[str] = None  # ["Monday", "Thursday"] for Planning Commission
    skip_holidays: bool = True
    custom_patterns: Dict[str, Any] = None

    def __post_init__(self):
        if self.meeting_days is None:
            self.meeting_days = []
        if self.custom_patterns is None:
            self.custom_patterns = {}

@dataclass
class HolidayConfig:
    """City holiday configuration - when to skip polling"""
    skip_holidays: bool = True
    federal_holidays: bool = True
    city_holidays: List[str] = None  # Additional city-specific dates
    holiday_buffer_days: int = 1  # Skip day before/after holidays

    def __post_init__(self):
        if self.city_holidays is None:
            self.city_holidays = []

class AdaptivePoller:
    """Main adaptive polling orchestrator"""

    def __init__(self, config_file: str = "data/polling_config.json"):
        self.config_file = Path(config_file)
        self.schedules: Dict[str, PollingSchedule] = {}
        self.holiday_config = HolidayConfig()
        self.logger = logging.getLogger(__name__)

        # Load existing configuration
        self._load_config()

        # Set up default schedules if none exist
        if not self.schedules:
            self._create_default_schedules()

    def _load_config(self):
        """Load polling configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)

                # Load schedules
                for source_name, schedule_data in config_data.get('schedules', {}).items():
                    # Convert datetime strings back to datetime objects
                    for field in ['last_attempt', 'last_success', 'next_scheduled']:
                        if schedule_data.get(field):
                            schedule_data[field] = datetime.fromisoformat(schedule_data[field])

                    # Convert time string back to time object
                    if schedule_data.get('preferred_time'):
                        time_str = schedule_data['preferred_time']
                        hour, minute = map(int, time_str.split(':'))
                        schedule_data['preferred_time'] = time(hour, minute)

                    self.schedules[source_name] = PollingSchedule(**schedule_data)

                # Load holiday config
                if 'holiday_config' in config_data:
                    self.holiday_config = HolidayConfig(**config_data['holiday_config'])

                self.logger.info(f"Loaded configuration for {len(self.schedules)} sources")

            except Exception as e:
                self.logger.error(f"Error loading polling config: {e}")
                self._create_default_schedules()
        else:
            self.logger.info("No existing config found, creating defaults")
            self._create_default_schedules()

    def _create_default_schedules(self):
        """Create default polling schedules for known Jacksonville sources"""

        # Planning Commission: meets 1st & 3rd Thursdays at 1 PM
        self.schedules["planning_commission"] = PollingSchedule(
            source_name="planning_commission",
            frequency=PollingFrequency.WEEKLY,
            preferred_time=time(7, 0),  # Check at 7 AM Friday morning
            meeting_days=["Thursday"],
            custom_patterns={"agenda_day_offset": 1}  # Check day after meetings
        )

        # City Council: meets 2nd & 4th Tuesdays at 5 PM
        self.schedules["city_council"] = PollingSchedule(
            source_name="city_council",
            frequency=PollingFrequency.WEEKLY,
            preferred_time=time(8, 0),  # Check at 8 AM Wednesday morning
            meeting_days=["Tuesday"],
            custom_patterns={"agenda_day_offset": 1}
        )

        # Development Services: irregular PDF releases
        self.schedules["development_services"] = PollingSchedule(
            source_name="development_services",
            frequency=PollingFrequency.BIWEEKLY,
            preferred_time=time(9, 0),
            meeting_days=[],
            custom_patterns={"check_multiple_formats": True}
        )

        # Public Works: monthly project updates
        self.schedules["public_works"] = PollingSchedule(
            source_name="public_works",
            frequency=PollingFrequency.MONTHLY,
            preferred_time=time(10, 0),
            meeting_days=[],
            custom_patterns={"first_monday_of_month": True}
        )

        self.logger.info("Created default polling schedules")
        self._save_config()

    def _save_config(self):
        """Save current configuration to file"""
        try:
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert to serializable format
            config_data = {
                "schedules": {},
                "holiday_config": asdict(self.holiday_config),
                "last_updated": datetime.now().isoformat()
            }

            for source_name, schedule in self.schedules.items():
                schedule_dict = asdict(schedule)

                # Convert datetime objects to ISO strings
                for field in ['last_attempt', 'last_success', 'next_scheduled']:
                    if schedule_dict.get(field):
                        schedule_dict[field] = schedule_dict[field].isoformat()

                # Convert time object to string
                if schedule_dict.get('preferred_time'):
                    time_obj = schedule_dict['preferred_time']
                    schedule_dict['preferred_time'] = f"{time_obj.hour:02d}:{time_obj.minute:02d}"

                config_data["schedules"][source_name] = schedule_dict

            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)

            self.logger.debug(f"Saved polling configuration to {self.config_file}")

        except Exception as e:
            self.logger.error(f"Error saving polling config: {e}")

    def is_holiday(self, check_date: datetime) -> bool:
        """Check if a date is a holiday when polling should be skipped"""

        if not self.holiday_config.skip_holidays:
            return False

        # Simple federal holiday check (extend as needed)
        federal_holidays_2024_2025 = [
            "2024-01-01", "2024-01-15", "2024-02-19", "2024-05-27",
            "2024-07-04", "2024-09-02", "2024-10-14", "2024-11-11",
            "2024-11-28", "2024-12-25",
            "2025-01-01", "2025-01-20", "2025-02-17", "2025-05-26",
            "2025-07-04", "2025-09-01", "2025-10-13", "2025-11-11",
            "2025-11-27", "2025-12-25"
        ]

        date_str = check_date.strftime("%Y-%m-%d")

        # Check federal holidays
        if self.holiday_config.federal_holidays and date_str in federal_holidays_2024_2025:
            return True

        # Check city-specific holidays
        if date_str in self.holiday_config.city_holidays:
            return True

        # Check holiday buffer (day before/after)
        if self.holiday_config.holiday_buffer_days > 0:
            for offset in range(-self.holiday_config.holiday_buffer_days,
                              self.holiday_config.holiday_buffer_days + 1):
                if offset == 0:
                    continue
                buffer_date = check_date + timedelta(days=offset)
                buffer_str = buffer_date.strftime("%Y-%m-%d")

                if (buffer_str in federal_holidays_2024_2025 or
                    buffer_str in self.holiday_config.city_holidays):
                    return True

        return False

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