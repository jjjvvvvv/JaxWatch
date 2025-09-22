#!/usr/bin/env python3
"""
JaxWatch Alert System
Handles Slack notifications for pipeline failures and important events
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
import requests


class AlertLevel(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of alerts"""
    VALIDATION_FAILURE = "validation_failure"
    PIPELINE_FAILURE = "pipeline_failure"
    RARE_DOCUMENT = "rare_document"
    SYSTEM_HEALTH = "system_health"
    DATA_QUALITY = "data_quality"


class SlackAlerter:
    """Handles Slack notifications with structured formatting"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')
        self.logger = logging.getLogger(__name__)

        if not self.webhook_url:
            self.logger.warning("No Slack webhook URL configured - alerts will be logged only")

    def send_alert(self,
                   level: AlertLevel,
                   alert_type: AlertType,
                   message: str,
                   board: Optional[str] = None,
                   date: Optional[str] = None,
                   link: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send structured alert to Slack"""

        alert_data = {
            "timestamp": datetime.now().isoformat(),
            "level": level.value,
            "type": alert_type.value,
            "message": message,
            "board": board,
            "date": date,
            "link": link,
            "metadata": metadata or {}
        }

        # Log the alert locally regardless of Slack status
        log_level = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL
        }.get(level, logging.INFO)

        self.logger.log(log_level, f"Alert: {alert_type.value} - {message}")

        if not self.webhook_url:
            return False

        try:
            slack_payload = self._format_slack_message(alert_data)
            response = requests.post(
                self.webhook_url,
                json=slack_payload,
                timeout=10
            )
            response.raise_for_status()
            return True

        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}")
            return False

    def _format_slack_message(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format alert data into Slack message payload"""

        # Color coding for different alert levels
        colors = {
            AlertLevel.INFO: "#36a64f",      # Green
            AlertLevel.WARNING: "#ff9800",   # Orange
            AlertLevel.ERROR: "#f44336",     # Red
            AlertLevel.CRITICAL: "#9c27b0"   # Purple
        }

        # Emoji for alert types
        emojis = {
            AlertType.VALIDATION_FAILURE: "⚠️",
            AlertType.PIPELINE_FAILURE: "🚨",
            AlertType.RARE_DOCUMENT: "📋",
            AlertType.SYSTEM_HEALTH: "💊",
            AlertType.DATA_QUALITY: "🔍"
        }

        level = AlertLevel(alert_data["level"])
        alert_type = AlertType(alert_data["type"])

        # Build attachment fields
        fields = []

        if alert_data["board"]:
            fields.append({
                "title": "Board/Source",
                "value": alert_data["board"],
                "short": True
            })

        if alert_data["date"]:
            fields.append({
                "title": "Date",
                "value": alert_data["date"],
                "short": True
            })

        if alert_data["link"]:
            fields.append({
                "title": "Link",
                "value": f"<{alert_data['link']}|View Document>",
                "short": False
            })

        # Add metadata fields
        for key, value in alert_data["metadata"].items():
            if value is not None:
                fields.append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value),
                    "short": True
                })

        attachment = {
            "color": colors.get(level, "#cccccc"),
            "title": f"{emojis.get(alert_type, '📢')} {alert_type.value.replace('_', ' ').title()}",
            "text": alert_data["message"],
            "fields": fields,
            "footer": "JaxWatch Municipal Observatory",
            "ts": int(datetime.now().timestamp())
        }

        return {
            "text": f"JaxWatch Alert: {level.value.upper()}",
            "attachments": [attachment]
        }


# Global alerter instance
_alerter = None


def get_alerter() -> SlackAlerter:
    """Get global alerter instance"""
    global _alerter
    if _alerter is None:
        _alerter = SlackAlerter()
    return _alerter


# Convenience functions for common alert types
def alert_validation_failure(source: str, project_id: str, error: str, **kwargs):
    """Alert for schema validation failures"""
    alerter = get_alerter()
    return alerter.send_alert(
        level=AlertLevel.ERROR,
        alert_type=AlertType.VALIDATION_FAILURE,
        message=f"Schema validation failed for project {project_id} from {source}",
        board=source,
        metadata={"project_id": project_id, "error": str(error)},
        **kwargs
    )


def alert_pipeline_failure(source: str, error: str, **kwargs):
    """Alert for pipeline execution failures"""
    alerter = get_alerter()
    return alerter.send_alert(
        level=AlertLevel.CRITICAL,
        alert_type=AlertType.PIPELINE_FAILURE,
        message=f"Pipeline failure in {source}",
        board=source,
        metadata={"error": str(error)},
        **kwargs
    )


def alert_rare_document(source: str, document_type: str, link: str = None, **kwargs):
    """Alert for rare or important document detection"""
    alerter = get_alerter()

    # Merge metadata from kwargs with default metadata
    default_metadata = {"document_type": document_type}
    if "metadata" in kwargs:
        # Merge with provided metadata, giving precedence to provided values
        metadata = {**default_metadata, **kwargs.pop("metadata")}
    else:
        metadata = default_metadata

    return alerter.send_alert(
        level=AlertLevel.INFO,
        alert_type=AlertType.RARE_DOCUMENT,
        message=f"Rare document detected: {document_type} in {source}",
        board=source,
        link=link,
        metadata=metadata,
        **kwargs
    )


def alert_system_health(issue: str, severity: AlertLevel = AlertLevel.WARNING, **kwargs):
    """Alert for system health issues"""
    alerter = get_alerter()
    return alerter.send_alert(
        level=severity,
        alert_type=AlertType.SYSTEM_HEALTH,
        message=f"System health issue: {issue}",
        **kwargs
    )


def alert_data_quality(source: str, issue: str, **kwargs):
    """Alert for data quality issues"""
    alerter = get_alerter()
    return alerter.send_alert(
        level=AlertLevel.WARNING,
        alert_type=AlertType.DATA_QUALITY,
        message=f"Data quality issue in {source}: {issue}",
        board=source,
        **kwargs
    )


# Configuration helper
def configure_alerts(webhook_url: str = None):
    """Configure the alert system"""
    global _alerter
    _alerter = SlackAlerter(webhook_url)


if __name__ == "__main__":
    # Test the alert system
    import argparse

    parser = argparse.ArgumentParser(description="Test JaxWatch alert system")
    parser.add_argument("--webhook", help="Slack webhook URL for testing")
    parser.add_argument("--test-type", default="info",
                        choices=["info", "warning", "error", "critical"],
                        help="Test alert level")

    args = parser.parse_args()

    if args.webhook:
        configure_alerts(args.webhook)

    # Send test alert
    alerter = get_alerter()
    success = alerter.send_alert(
        level=AlertLevel(args.test_type),
        alert_type=AlertType.SYSTEM_HEALTH,
        message="Test alert from JaxWatch alert system",
        board="test_source",
        date="2025-09-20",
        metadata={"test": True, "timestamp": datetime.now().isoformat()}
    )

    print(f"Test alert sent: {'Success' if success else 'Failed'}")