#!/usr/bin/env python3
"""
DEPRECATED (non-MVP): Source Health Monitor

Moved to experiments/advanced/source_health_monitor.py.
Importing this module without explicitly enabling advanced features will raise.
"""

import os as _os

if _os.getenv("JAXWATCH_ADVANCED", "0").lower() in {"1", "true", "yes", "on"}:
    # Allow opt-in import path for backwards compatibility
    from experiments.advanced.source_health_monitor import *  # noqa: F401,F403
else:
    raise ImportError(
        "Source health monitor is non-MVP and has moved to experiments/advanced. "
        "Set JAXWATCH_ADVANCED=1 or import experiments.advanced.source_health_monitor."
    )

    def get_system_health_summary(self) -> SystemHealthSummary:
        """Get overall system health summary."""
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
                last_updated=datetime.now()
            )

        # Count sources by status
        status_counts = Counter(source.status for source in all_sources)

        # Calculate overall success rate
        total_success_rates = [source.success_rate_24h for source in all_sources if source.success_rate_24h >= 0]
        overall_success_rate = statistics.mean(total_success_rates) if total_success_rates else 0.0

        # Determine overall status
        if status_counts[SourceHealthStatus.CRITICAL] > 0:
            overall_status = SourceHealthStatus.CRITICAL
        elif status_counts[SourceHealthStatus.WARNING] > 0:
            overall_status = SourceHealthStatus.WARNING
        elif status_counts[SourceHealthStatus.HEALTHY] > 0:
            overall_status = SourceHealthStatus.HEALTHY
        else:
            overall_status = SourceHealthStatus.UNKNOWN

        # Total documents processed
        total_docs = sum(source.total_documents_processed for source in all_sources)

        return SystemHealthSummary(
            overall_status=overall_status,
            healthy_sources=status_counts[SourceHealthStatus.HEALTHY],
            warning_sources=status_counts[SourceHealthStatus.WARNING],
            critical_sources=status_counts[SourceHealthStatus.CRITICAL],
            total_sources=len(all_sources),
            overall_success_rate=overall_success_rate,
            total_documents_processed=total_docs,
            last_updated=datetime.now()
        )

    def _calculate_success_rate(self, polls: List) -> float:
        """Calculate success rate from poll attempts."""
        if not polls:
            return -1.0  # Unknown

        successful = sum(1 for p in polls if p['success'])
        return (successful / len(polls)) * 100.0

    def _count_consecutive_failures(self, polls: List) -> int:
        """Count consecutive failures from most recent polls."""
        consecutive = 0
        for poll in polls:  # Already sorted by timestamp DESC
            if not poll['success']:
                consecutive += 1
            else:
                break
        return consecutive

    def _calculate_health_score(self, success_rate_24h: float, success_rate_7d: float,
                              consecutive_failures: int, last_successful: str,
                              avg_response_time: float) -> float:
        """Calculate overall health score (0-100)."""
        score = 100.0

        # Deduct for low success rates
        if success_rate_24h >= 0:
            score *= (success_rate_24h / 100.0)

        if success_rate_7d >= 0:
            score *= (success_rate_7d / 100.0) * 0.5 + 0.5  # Less weight than 24h

        # Deduct for consecutive failures
        if consecutive_failures > 0:
            score *= max(0.1, 1.0 - (consecutive_failures * 0.2))

        # Deduct for stale data
        if last_successful:
            last_success_time = self._parse_datetime(last_successful)
            if last_success_time:
                hours_since_success = (datetime.now() - last_success_time).total_seconds() / 3600
                if hours_since_success > 24:
                    staleness_penalty = min(0.8, hours_since_success / 24 * 0.1)
                    score *= (1.0 - staleness_penalty)

        # Deduct for slow response times
        if avg_response_time > 10000:  # 10+ seconds is concerning
            score *= 0.8
        elif avg_response_time > 30000:  # 30+ seconds is very concerning
            score *= 0.5

        return max(0.0, score)

    def _determine_health_status(self, health_score: float, consecutive_failures: int) -> SourceHealthStatus:
        """Determine health status from score and other factors."""
        if consecutive_failures >= 5:
            return SourceHealthStatus.CRITICAL
        elif health_score >= 80:
            return SourceHealthStatus.HEALTHY
        elif health_score >= 50:
            return SourceHealthStatus.WARNING
        else:
            return SourceHealthStatus.CRITICAL

    def _generate_recommendations(self, status: SourceHealthStatus,
                                success_rate_24h: float, success_rate_7d: float,
                                consecutive_failures: int, last_successful: str,
                                avg_response_time: float) -> List[str]:
        """Generate actionable recommendations based on health metrics."""
        recommendations = []

        if status == SourceHealthStatus.CRITICAL:
            if consecutive_failures >= 5:
                recommendations.append("Check if the data source website is accessible")
                recommendations.append("Verify if the source has changed their document publishing location")

            if success_rate_24h < 20:
                recommendations.append("Consider increasing polling interval to reduce server load")
                recommendations.append("Check for anti-bot measures or rate limiting")

        elif status == SourceHealthStatus.WARNING:
            if success_rate_24h < 80:
                recommendations.append("Monitor closely - success rate declining")

            if avg_response_time > 15000:
                recommendations.append("Source responding slowly - consider timeout adjustments")

        if last_successful:
            last_success_time = self._parse_datetime(last_successful)
            if last_success_time:
                hours_since = (datetime.now() - last_success_time).total_seconds() / 3600
                if hours_since > 48:
                    recommendations.append("No successful polls in over 48 hours - investigate urgently")
                elif hours_since > 24:
                    recommendations.append("No successful polls in over 24 hours - check source")

        if not recommendations:
            recommendations.append("Source operating normally")

        return recommendations

    def _parse_datetime(self, dt_string: str) -> Optional[datetime]:
        """Parse datetime string safely."""
        if not dt_string:
            return None
        try:
            return datetime.fromisoformat(dt_string)
        except (ValueError, TypeError):
            return None

    def export_health_report(self, output_path: Path = None) -> Dict[str, Any]:
        """Export comprehensive health report."""
        output_path = output_path or (self.data_dir / "health_report.json")

        system_summary = self.get_system_health_summary()
        all_sources = self.get_all_sources_health()

        # Convert enums to strings for JSON serialization
        def convert_for_json(obj):
            if hasattr(obj, '__dict__'):
                result = {}
                for key, value in obj.__dict__.items():
                    if hasattr(value, 'value'):  # Enum
                        result[key] = value.value
                    elif isinstance(value, datetime):
                        result[key] = value.isoformat() if value else None
                    else:
                        result[key] = value
                return result
            return obj

        report = {
            "report_generated": datetime.now().isoformat(),
            "system_summary": convert_for_json(system_summary),
            "source_details": [convert_for_json(source) for source in all_sources],
            "recommendations": {
                "immediate_action": [],
                "monitoring": [],
                "optimization": []
            }
        }

        # Categorize recommendations
        for source in all_sources:
            for rec in source.recommendations:
                if "urgently" in rec or "critical" in rec.lower():
                    report["recommendations"]["immediate_action"].append(f"{source.source_name}: {rec}")
                elif "monitor" in rec.lower() or "check" in rec.lower():
                    report["recommendations"]["monitoring"].append(f"{source.source_name}: {rec}")
                else:
                    report["recommendations"]["optimization"].append(f"{source.source_name}: {rec}")

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        return report

    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old health data to prevent database bloat."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        with sqlite3.connect(self.health_db_path) as conn:
            # Keep recent data and any critical failure events
            conn.execute("""
                DELETE FROM poll_attempts
                WHERE timestamp < ? AND success = 1
            """, (cutoff_date,))

            conn.execute("""
                DELETE FROM processing_events
                WHERE timestamp < ? AND success = 1
            """, (cutoff_date,))

            conn.execute("VACUUM")

def main():
    """CLI interface for health monitoring."""
    import argparse

    parser = argparse.ArgumentParser(description="JaxWatch Source Health Monitor")
    parser.add_argument("--status", action="store_true", help="Show system health status")
    parser.add_argument("--source", help="Show detailed metrics for specific source")
    parser.add_argument("--export", help="Export health report to file")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", help="Clean up data older than N days")
    parser.add_argument("--web", action="store_true", help="Start web dashboard")
    parser.add_argument("--port", type=int, default=5003, help="Web dashboard port")

    args = parser.parse_args()

    monitor = SourceHealthMonitor()

    if args.status:
        summary = monitor.get_system_health_summary()
        print(f"\n🏥 JaxWatch System Health Status")
        print(f"Overall Status: {summary.overall_status.value.upper()}")
        print(f"Sources: {summary.healthy_sources} healthy, {summary.warning_sources} warning, {summary.critical_sources} critical")
        print(f"Success Rate: {summary.overall_success_rate:.1f}%")
        print(f"Total Documents: {summary.total_documents_processed}")
        print(f"Last Updated: {summary.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")

        # Show critical sources
        all_sources = monitor.get_all_sources_health()
        critical_sources = [s for s in all_sources if s.status == SourceHealthStatus.CRITICAL]
        if critical_sources:
            print(f"\n🚨 Critical Sources:")
            for source in critical_sources:
                print(f"  - {source.source_name}: {source.recommendations[0] if source.recommendations else 'Unknown issue'}")

    elif args.source:
        metrics = monitor.get_source_health_metrics(args.source)
        print(f"\n📊 Health Metrics for {metrics.source_name}")
        print(f"Status: {metrics.status.value.upper()}")
        print(f"Health Score: {metrics.health_score:.1f}/100")
        print(f"Success Rate (24h): {metrics.success_rate_24h:.1f}%")
        print(f"Success Rate (7d): {metrics.success_rate_7d:.1f}%")
        print(f"Consecutive Failures: {metrics.consecutive_failures}")
        print(f"Avg Response Time: {metrics.average_response_time:.0f}ms")
        print(f"Documents Processed: {metrics.total_documents_processed} total, {metrics.documents_processed_7d} this week")

        if metrics.last_successful_poll:
            print(f"Last Successful Poll: {metrics.last_successful_poll.strftime('%Y-%m-%d %H:%M:%S')}")

        if metrics.last_error_message:
            print(f"Last Error: {metrics.last_error_message}")

        if metrics.recommendations:
            print(f"\nRecommendations:")
            for rec in metrics.recommendations:
                print(f"  - {rec}")

    elif args.export:
        report = monitor.export_health_report(Path(args.export))
        print(f"Health report exported to {args.export}")

    elif args.cleanup:
        monitor.cleanup_old_data(args.cleanup)
        print(f"Cleaned up data older than {args.cleanup} days")

    elif args.web:
        try:
            from flask import Flask, render_template_string, jsonify

            app = Flask(__name__)

            @app.route('/')
            def dashboard():
                return render_template_string("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>JaxWatch Health Dashboard</title>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
                        .container { max-width: 1200px; margin: 0 auto; }
                        .card { background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                        .status-healthy { color: #28a745; }
                        .status-warning { color: #ffc107; }
                        .status-critical { color: #dc3545; }
                        .status-unknown { color: #6c757d; }
                        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
                        .metric { text-align: center; padding: 15px; background: #f8f9fa; border-radius: 6px; }
                        .metric-value { font-size: 24px; font-weight: bold; margin-bottom: 5px; }
                        .metric-label { font-size: 14px; color: #666; }
                        .source-list { display: grid; gap: 15px; }
                        .source-item { display: flex; justify-content: space-between; align-items: center; padding: 15px; background: #f8f9fa; border-radius: 6px; }
                        .recommendations { margin-top: 15px; }
                        .recommendations ul { margin: 10px 0; padding-left: 20px; }
                        .refresh-btn { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🏥 JaxWatch Health Dashboard</h1>
                        <button class="refresh-btn" onclick="location.reload()">Refresh</button>

                        <div id="health-data">
                            <p>Loading health data...</p>
                        </div>
                    </div>

                    <script>
                        async function loadHealthData() {
                            try {
                                const response = await fetch('/api/health');
                                const data = await response.json();

                                document.getElementById('health-data').innerHTML = `
                                    <div class="card">
                                        <h2>System Overview</h2>
                                        <div class="metrics">
                                            <div class="metric">
                                                <div class="metric-value status-${data.system_summary.overall_status}">${data.system_summary.overall_status.toUpperCase()}</div>
                                                <div class="metric-label">Overall Status</div>
                                            </div>
                                            <div class="metric">
                                                <div class="metric-value">${data.system_summary.total_sources}</div>
                                                <div class="metric-label">Total Sources</div>
                                            </div>
                                            <div class="metric">
                                                <div class="metric-value">${data.system_summary.overall_success_rate.toFixed(1)}%</div>
                                                <div class="metric-label">Success Rate</div>
                                            </div>
                                            <div class="metric">
                                                <div class="metric-value">${data.system_summary.total_documents_processed}</div>
                                                <div class="metric-label">Documents Processed</div>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="card">
                                        <h2>Source Status</h2>
                                        <div class="source-list">
                                            ${data.source_details.map(source => `
                                                <div class="source-item">
                                                    <div>
                                                        <strong>${source.source_name}</strong>
                                                        <div style="font-size: 14px; color: #666;">
                                                            Success: ${source.success_rate_24h.toFixed(1)}% |
                                                            Health: ${source.health_score.toFixed(0)}/100 |
                                                            Docs: ${source.documents_processed_7d} this week
                                                        </div>
                                                    </div>
                                                    <div class="status-${source.status}">${source.status.toUpperCase()}</div>
                                                </div>
                                            `).join('')}
                                        </div>
                                    </div>

                                    ${data.recommendations.immediate_action.length > 0 ? `
                                        <div class="card">
                                            <h2>🚨 Immediate Action Required</h2>
                                            <ul>
                                                ${data.recommendations.immediate_action.map(rec => `<li>${rec}</li>`).join('')}
                                            </ul>
                                        </div>
                                    ` : ''}

                                    ${data.recommendations.monitoring.length > 0 ? `
                                        <div class="card">
                                            <h2>👀 Monitoring Recommendations</h2>
                                            <ul>
                                                ${data.recommendations.monitoring.map(rec => `<li>${rec}</li>`).join('')}
                                            </ul>
                                        </div>
                                    ` : ''}
                                `;
                            } catch (error) {
                                document.getElementById('health-data').innerHTML = '<p>Error loading health data</p>';
                            }
                        }

                        loadHealthData();

                        // Auto-refresh every 5 minutes
                        setInterval(loadHealthData, 300000);
                    </script>
                </body>
                </html>
                """)

            @app.route('/api/health')
            def api_health():
                return jsonify(monitor.export_health_report())

            print(f"🌐 Starting health dashboard at http://localhost:{args.port}")
            app.run(host='0.0.0.0', port=args.port, debug=False)

        except ImportError:
            print("Flask not available. Install with: pip install flask")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
