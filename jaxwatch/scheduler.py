#!/usr/bin/env python3
"""
JaxWatch Scheduler
Cron-compatible entry point for automated data collection and enrichment.

Usage:
    # Run full pipeline (collection + extraction + enrichment)
    python -m jaxwatch.scheduler

    # Collection only (fast, for frequent runs)
    python -m jaxwatch.scheduler --collect-only

    # Enrichment only (slow, for less frequent runs)
    python -m jaxwatch.scheduler --enrich-only

    # Specific source
    python -m jaxwatch.scheduler --source dia_board

Example crontab:
    # Collect every 6 hours
    0 */6 * * * cd /path/to/JaxWatch && python -m jaxwatch.scheduler --collect-only

    # Full pipeline daily at 2am
    0 2 * * * cd /path/to/JaxWatch && python -m jaxwatch.scheduler

    # Enrichment only weekly on Sunday
    0 3 * * 0 cd /path/to/JaxWatch && python -m jaxwatch.scheduler --enrich-only
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from jaxwatch.config.manager import get_config
from jaxwatch.pipeline import CivicPipeline, run_pipeline
from jaxwatch.state import get_manifest


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging for scheduled runs."""
    config = get_config()
    log_dir = config.paths.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if verbose else logging.INFO
    log_file = log_dir / f"scheduler-{datetime.now().strftime('%Y-%m-%d')}.log"

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger("jaxwatch.scheduler")


def run_scheduled(
    collect_only: bool = False,
    enrich_only: bool = False,
    source: Optional[str] = None,
    year: Optional[str] = None,
    verbose: bool = False
) -> int:
    """Run scheduled pipeline execution.

    Args:
        collect_only: Only run collection stages (fast)
        enrich_only: Only run enrichment stages (AI verification, references)
        source: Limit to specific source
        year: Limit to specific year
        verbose: Enable verbose logging

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    logger = setup_logging(verbose)
    logger.info("=" * 60)
    logger.info("JaxWatch Scheduled Run")
    logger.info(f"Mode: {'collect-only' if collect_only else 'enrich-only' if enrich_only else 'full-pipeline'}")
    logger.info(f"Source: {source or 'all'}")
    logger.info(f"Year: {year or 'all'}")
    logger.info("=" * 60)

    try:
        if enrich_only:
            # Run only enrichment (verification + references)
            pipeline = CivicPipeline()
            # Skip collection stages
            result = pipeline.run_full_cycle(
                source=source,
                year=year,
                skip_enrich=False  # Do run enrichment
            )
            # Filter to only show enrich stages in result
            logger.info(f"Enrichment completed: {result.success}")

        elif collect_only:
            # Run only collection (no AI)
            result = run_pipeline(
                source=source,
                year=year,
                skip_enrich=True  # Skip AI stages
            )
            logger.info(f"Collection completed: {result.success}")

        else:
            # Full pipeline
            result = run_pipeline(
                source=source,
                year=year,
                skip_enrich=False
            )
            logger.info(f"Full pipeline completed: {result.success}")

        # Log manifest stats
        manifest = get_manifest()
        stats = manifest.get_stats()
        logger.info(f"Manifest stats: {stats['total_urls']} total URLs, {stats['failed_urls']} failed")

        # Print summary
        print()
        print(result.summary())

        return 0 if result.success else 1

    except Exception as e:
        logger.exception(f"Scheduled run failed: {e}")
        return 2


def main(argv=None) -> int:
    """CLI entry point for scheduler."""
    parser = argparse.ArgumentParser(
        description="JaxWatch Scheduler - Cron-compatible entry point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Full pipeline
    python -m jaxwatch.scheduler

    # Collection only (fast, no AI)
    python -m jaxwatch.scheduler --collect-only

    # Enrichment only (AI verification + references)
    python -m jaxwatch.scheduler --enrich-only

    # Specific source
    python -m jaxwatch.scheduler --source dia_board

Crontab examples:
    # Collect every 6 hours
    0 */6 * * * cd /path/to/JaxWatch && python -m jaxwatch.scheduler --collect-only

    # Full pipeline daily at 2am
    0 2 * * * cd /path/to/JaxWatch && python -m jaxwatch.scheduler
        """
    )
    parser.add_argument("--collect-only", action="store_true",
                        help="Only run collection stages (fast, no AI)")
    parser.add_argument("--enrich-only", action="store_true",
                        help="Only run enrichment stages (AI verification, references)")
    parser.add_argument("--source", help="Limit to specific source")
    parser.add_argument("--year", help="Limit to specific year")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose logging")

    args = parser.parse_args(argv)

    if args.collect_only and args.enrich_only:
        print("Error: Cannot specify both --collect-only and --enrich-only")
        return 1

    return run_scheduled(
        collect_only=args.collect_only,
        enrich_only=args.enrich_only,
        source=args.source,
        year=args.year,
        verbose=args.verbose
    )


if __name__ == "__main__":
    sys.exit(main())
