#!/usr/bin/env python3
"""
Source Health Monitor for JaxWatch Municipal Data Observatory

Moved from backend/common to experiments/advanced as non-MVP functionality.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import statistics
from collections import defaultdict, Counter


class SourceHealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class SourceHealthMetrics:
    source_name: str
    status: 'SourceHealthStatus'
    last_successful_poll: Optional[datetime]
    last_attempted_poll: Optional[datetime]
    success_rate_24h: float
    success_rate_7d: float
    consecutive_failures: int
    average_response_time: float
    total_documents_processed: int
    documents_processed_7d: int
    last_error_message: Optional[str]
    next_scheduled_poll: Optional[datetime]
    health_score: float  # 0-100
    recommendations: List[str]


@dataclass
class SystemHealthSummary:
    overall_status: 'SourceHealthStatus'
    healthy_sources: int
    warning_sources: int
    critical_sources: int
    total_sources: int
    overall_success_rate: float
    total_documents_processed: int
    last_updated: datetime


class SourceHealthMonitor:
    """Monitor and track health metrics for all municipal data sources."""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data")
        self.health_db_path = self.data_dir / "source_health.db"
        self.data_dir.mkdir(exist_ok=True)
        self._init_database()

    def _init_database(self):
        with sqlite3.connect(self.health_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS poll_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    success BOOLEAN NOT NULL,
                    response_time_ms INTEGER,
                    error_message TEXT,
                    documents_found INTEGER DEFAULT 0,
                    new_documents INTEGER DEFAULT 0
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    event_type TEXT NOT NULL,
                    document_id TEXT,
                    metadata TEXT,
                    success BOOLEAN NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_poll_attempts_source_time
                ON poll_attempts(source_name, timestamp)
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_processing_events_source_time
                ON processing_events(source_name, timestamp)
                """
            )

    def record_poll_attempt(
        self,
        source_name: str,
        success: bool,
        response_time_ms: int = None,
        error_message: str = None,
        documents_found: int = 0,
        new_documents: int = 0,
    ):
        with sqlite3.connect(self.health_db_path) as conn:
            conn.execute(
                """
                INSERT INTO poll_attempts
                (source_name, timestamp, success, response_time_ms, error_message,
                 documents_found, new_documents)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_name,
                    datetime.now(),
                    success,
                    response_time_ms,
                    error_message,
                    documents_found,
                    new_documents,
                ),
            )

    def record_processing_event(
        self,
        source_name: str,
        event_type: str,
        success: bool,
        document_id: str = None,
        metadata: Dict[str, Any] = None,
    ):
        with sqlite3.connect(self.health_db_path) as conn:
            conn.execute(
                """
                INSERT INTO processing_events
                (source_name, timestamp, event_type, document_id, metadata, success)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source_name,
                    datetime.now(),
                    event_type,
                    document_id,
                    json.dumps(metadata) if metadata else None,
                    success,
                ),
            )

    def get_source_health_metrics(self, source_name: str) -> 'SourceHealthMetrics':
        now = datetime.now()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        with sqlite3.connect(self.health_db_path) as conn:
            conn.row_factory = sqlite3.Row

            polls_24h = conn.execute(
                """
                SELECT * FROM poll_attempts
                WHERE source_name = ? AND timestamp > ?
                ORDER BY timestamp DESC
                """,
                (source_name, day_ago),
            ).fetchall()

            polls_7d = conn.execute(
                """
                SELECT * FROM poll_attempts
                WHERE source_name = ? AND timestamp > ?
                ORDER BY timestamp DESC
                """,
                (source_name, week_ago),
            ).fetchall()

            processing_events = conn.execute(
                """
                SELECT * FROM processing_events
                WHERE source_name = ?
                ORDER BY timestamp DESC
                """,
                (source_name,),
            ).fetchall()

            processing_7d = conn.execute(
                """
                SELECT * FROM processing_events
                WHERE source_name = ? AND timestamp > ?
                ORDER BY timestamp DESC
                """,
                (source_name, week_ago),
            ).fetchall()

        success_rate_24h = self._calculate_success_rate(polls_24h)
        success_rate_7d = self._calculate_success_rate(polls_7d)
        consecutive_failures = self._count_consecutive_failures(polls_7d)

        successful_polls = [p for p in polls_7d if p['success'] and p['response_time_ms']]
        avg_response_time = (
            statistics.mean(p['response_time_ms'] for p in successful_polls) if successful_polls else 0.0
        )

        total_docs = len([e for e in processing_events if e['event_type'] == 'document_processed'])
        docs_7d = len([e for e in processing_7d if e['event_type'] == 'document_processed'])

        last_attempted = polls_7d[0]['timestamp'] if polls_7d else None
        successful_polls_recent = [p for p in polls_7d if p['success']]
        last_successful = successful_polls_recent[0]['timestamp'] if successful_polls_recent else None

        failed_polls = [p for p in polls_7d if not p['success'] and p['error_message']]
        last_error = failed_polls[0]['error_message'] if failed_polls else None

        health_score = self._calculate_health_score(
            success_rate_24h, success_rate_7d, consecutive_failures, last_successful, avg_response_time
        )
        status = self._determine_health_status(health_score, consecutive_failures)

        recommendations = self._generate_recommendations(
            status, success_rate_24h, success_rate_7d, consecutive_failures, last_successful, avg_response_time
        )

        return SourceHealthMetrics(
            source_name=source_name,
            status=status,
            last_successful_poll=self._parse_datetime(last_successful),
            last_attempted_poll=self._parse_datetime(last_attempted),
            success_rate_24h=success_rate_24h,
            success_rate_7d=success_rate_7d,
            consecutive_failures=consecutive_failures,
            average_response_time=avg_response_time,
            total_documents_processed=total_docs,
            documents_processed_7d=docs_7d,
            last_error_message=last_error,
            next_scheduled_poll=None,
            health_score=health_score,
            recommendations=recommendations,
        )

    def get_all_sources_health(self) -> List['SourceHealthMetrics']:
        with sqlite3.connect(self.health_db_path) as conn:
            sources = conn.execute(
                """
                SELECT DISTINCT source_name FROM poll_attempts
                """
            ).fetchall()
        return [self.get_source_health_metrics(source[0]) for source in sources]

    def get_system_health_summary(self) -> 'SystemHealthSummary':
        all_sources = self.get_all_sources_health()
        if not all_sources:
            return SystemHealthSummary(
                overall_status=SourceHealthStatus.UNKNOWN,
                healthy_sources=0,
                warning_sources=0,
                critical_sources=0,
                total_sources=0,
                overall_success_rate=0.0,
                total_documents_processed=0,
                last_updated=datetime.now(),
            )

        status_counts = Counter(source.status for source in all_sources)
        total_success_rates = [source.success_rate_24h for source in all_sources if source.success_rate_24h >= 0]
        overall_success_rate = statistics.mean(total_success_rates) if total_success_rates else 0.0

        if status_counts[SourceHealthStatus.CRITICAL] > 0:
            overall_status = SourceHealthStatus.CRITICAL
        elif status_counts[SourceHealthStatus.WARNING] > 0:
            overall_status = SourceHealthStatus.WARNING
        elif status_counts[SourceHealthStatus.HEALTHY] > 0:
            overall_status = SourceHealthStatus.HEALTHY
        else:
            overall_status = SourceHealthStatus.UNKNOWN

        total_docs = sum(source.total_documents_processed for source in all_sources)

        return SystemHealthSummary(
            overall_status=overall_status,
            healthy_sources=status_counts[SourceHealthStatus.HEALTHY],
            warning_sources=status_counts[SourceHealthStatus.WARNING],
            critical_sources=status_counts[SourceHealthStatus.CRITICAL],
            total_sources=len(all_sources),
            overall_success_rate=overall_success_rate,
            total_documents_processed=total_docs,
            last_updated=datetime.now(),
        )

    def _calculate_success_rate(self, polls: List) -> float:
        if not polls:
            return -1.0
        successful = sum(1 for p in polls if p['success'])
        return (successful / len(polls)) * 100.0

    def _count_consecutive_failures(self, polls: List) -> int:
        consecutive = 0
        for poll in polls:
            if not poll['success']:
                consecutive += 1
            else:
                break
        return consecutive

    def _calculate_health_score(
        self,
        success_rate_24h: float,
        success_rate_7d: float,
        consecutive_failures: int,
        last_successful: str,
        avg_response_time: float,
    ) -> float:
        score = 100.0
        if success_rate_24h >= 0:
            score *= (success_rate_24h / 100.0)
        if success_rate_7d >= 0:
            score *= (success_rate_7d / 100.0) * 0.5 + 0.5
        if consecutive_failures > 0:
            score *= max(0.1, 1.0 - (consecutive_failures * 0.2))
        if last_successful:
            last_success_time = self._parse_datetime(last_successful)
            if last_success_time:
                hours_since_success = (datetime.now() - last_success_time).total_seconds() / 3600
                if hours_since_success > 24:
                    staleness_penalty = min(0.8, hours_since_success / 24 * 0.1)
                    score *= (1.0 - staleness_penalty)
        if avg_response_time > 10000:
            score *= 0.8
        elif avg_response_time > 30000:
            score *= 0.5
        return max(0.0, score)

    def _determine_health_status(self, health_score: float, consecutive_failures: int) -> 'SourceHealthStatus':
        if consecutive_failures >= 5:
            return SourceHealthStatus.CRITICAL
        elif health_score >= 80:
            return SourceHealthStatus.HEALTHY
        elif health_score >= 50:
            return SourceHealthStatus.WARNING
        else:
            return SourceHealthStatus.CRITICAL

    def _generate_recommendations(
        self,
        status: 'SourceHealthStatus',
        success_rate_24h: float,
        success_rate_7d: float,
        consecutive_failures: int,
        last_successful: str,
        avg_response_time: float,
    ) -> List[str]:
        recommendations: List[str] = []
        if status == SourceHealthStatus.CRITICAL:
            if consecutive_failures >= 5:
                recommendations.append("Check source availability and robots; reduce cadence if down.")
        if success_rate_24h >= 0 and success_rate_24h < 50:
            recommendations.append("Investigate recent failures; consider backoff.")
        if avg_response_time > 30000:
            recommendations.append("Responses slow; consider caching or reduced frequency.")
        return recommendations

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        try:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str) and value:
                return datetime.fromisoformat(value)
        except Exception:
            return None
        return None

    # Export and CLI are trimmed for brevity. Full version can be restored if needed.
    def export_health_report(self) -> Dict[str, Any]:
        sources = [asdict(m) for m in self.get_all_sources_health()]
        system = asdict(self.get_system_health_summary())
        return {"system_summary": system, "source_details": sources}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Source Health Monitor (advanced)")
    parser.add_argument("--status", action="store_true", help="Show system status")
    parser.add_argument("--source", help="Show details for a source")
    parser.add_argument("--export", help="Export JSON report to path")
    args = parser.parse_args()

    monitor = SourceHealthMonitor()
    if args.status:
        summary = monitor.get_system_health_summary()
        print(json.dumps(asdict(summary), default=str, indent=2))
    elif args.source:
        print(json.dumps(asdict(monitor.get_source_health_metrics(args.source)), default=str, indent=2))
    elif args.export:
        Path(args.export).parent.mkdir(parents=True, exist_ok=True)
        with open(args.export, "w") as f:
            json.dump(monitor.export_health_report(), f, indent=2, default=str)
        print(f"Exported to {args.export}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

