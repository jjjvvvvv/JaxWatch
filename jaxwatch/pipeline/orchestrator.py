#!/usr/bin/env python3
"""
JaxWatch Pipeline Orchestrator
Unified control plane for the full data pipeline.

Pipeline stages:
1. Collect - Scrape government websites for meeting data
2. Extract PDFs - Download and extract text from PDFs
3. Identify Projects - Extract project mentions from text
4. Enrich - AI verification and reference scanning
"""

import argparse
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from jaxwatch.config.manager import get_config, JaxWatchConfig

logger = logging.getLogger("jaxwatch.pipeline")


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""
    stage: str
    success: bool
    duration_seconds: float
    message: str = ""
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """Result of full pipeline execution."""
    started_at: datetime
    completed_at: Optional[datetime] = None
    stages: List[StageResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return all(s.success for s in self.stages)

    @property
    def duration_seconds(self) -> float:
        if self.completed_at is None:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()

    def summary(self) -> str:
        lines = [
            f"Pipeline {'SUCCEEDED' if self.success else 'FAILED'}",
            f"Duration: {self.duration_seconds:.1f}s",
            f"Stages: {len(self.stages)}",
            ""
        ]
        for stage in self.stages:
            status = "✓" if stage.success else "✗"
            lines.append(f"  {status} {stage.stage}: {stage.message} ({stage.duration_seconds:.1f}s)")
            if stage.error:
                lines.append(f"      Error: {stage.error}")
        return "\n".join(lines)


class CivicPipeline:
    """Orchestrator for the JaxWatch data pipeline.

    Runs stages in sequence:
    1. collect - Scrape government websites
    2. extract_pdfs - Download and extract PDF text
    3. extract_projects - Identify projects from text
    4. verify_documents - AI document verification (optional)
    5. scan_references - Detect document references (optional)
    """

    def __init__(self, config: Optional[JaxWatchConfig] = None):
        self.config = config or get_config()
        self.project_root = self.config.base_path

    def run_full_cycle(
        self,
        source: Optional[str] = None,
        year: Optional[str] = None,
        skip_enrich: bool = False,
        dry_run: bool = False
    ) -> PipelineResult:
        """Run the complete data pipeline.

        Args:
            source: Limit to specific source (e.g., 'dia_board')
            year: Limit to specific year
            skip_enrich: Skip AI enrichment stages (verification, references)
            dry_run: Print commands without executing

        Returns:
            PipelineResult with stage outcomes
        """
        result = PipelineResult(started_at=datetime.now())

        stages = [
            ("collect", lambda: self._run_collect(source, dry_run)),
            ("extract_pdfs", lambda: self._run_extract_pdfs(dry_run)),
            ("extract_projects", lambda: self._run_extract_projects(source, year, dry_run)),
        ]

        if not skip_enrich:
            stages.extend([
                ("verify_documents", lambda: self._run_verify_documents(year, dry_run)),
                ("scan_references", lambda: self._run_scan_references(source, year, dry_run)),
            ])

        for stage_name, stage_fn in stages:
            logger.info(f"Starting stage: {stage_name}")
            start = datetime.now()

            try:
                stage_result = stage_fn()
                duration = (datetime.now() - start).total_seconds()

                result.stages.append(StageResult(
                    stage=stage_name,
                    success=stage_result.get("success", True),
                    duration_seconds=duration,
                    message=stage_result.get("message", "completed"),
                    error=stage_result.get("error")
                ))

                if not stage_result.get("success", True):
                    logger.error(f"Stage {stage_name} failed, stopping pipeline")
                    break

            except Exception as e:
                duration = (datetime.now() - start).total_seconds()
                result.stages.append(StageResult(
                    stage=stage_name,
                    success=False,
                    duration_seconds=duration,
                    message="exception",
                    error=str(e)
                ))
                logger.exception(f"Stage {stage_name} raised exception")
                break

        result.completed_at = datetime.now()
        return result

    def _run_command(self, cmd: List[str], dry_run: bool = False) -> dict:
        """Run a shell command and return result."""
        cmd_str = " ".join(cmd)

        if dry_run:
            print(f"[DRY RUN] Would execute: {cmd_str}")
            return {"success": True, "message": "dry run"}

        try:
            proc = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout per stage
            )

            if proc.returncode != 0:
                return {
                    "success": False,
                    "message": f"exit code {proc.returncode}",
                    "error": proc.stderr[:500] if proc.stderr else None
                }

            return {"success": True, "message": "completed"}

        except subprocess.TimeoutExpired:
            return {"success": False, "message": "timeout", "error": "Stage timed out after 10 minutes"}
        except Exception as e:
            return {"success": False, "message": "exception", "error": str(e)}

    def _run_collect(self, source: Optional[str], dry_run: bool) -> dict:
        """Run collection stage."""
        cmd = ["python3", "-m", "backend.collector.engine",
               "--config", "backend/collector/sources.yaml"]
        if source:
            cmd.extend(["--source", source])
        return self._run_command(cmd, dry_run)

    def _run_extract_pdfs(self, dry_run: bool) -> dict:
        """Run PDF extraction stage."""
        cmd = ["python3", "-m", "backend.tools.pdf_extractor"]
        return self._run_command(cmd, dry_run)

    def _run_extract_projects(self, source: Optional[str], year: Optional[str], dry_run: bool) -> dict:
        """Run project extraction stage."""
        cmd = ["python3", "-m", "backend.tools.extract_projects"]
        if source:
            cmd.extend(["--source", source])
        if year:
            cmd.extend(["--year", year])
        return self._run_command(cmd, dry_run)

    def _run_verify_documents(self, year: Optional[str], dry_run: bool) -> dict:
        """Run document verification stage."""
        cmd = ["python3", "-m", "document_verifier.commands.summarize"]
        if year:
            cmd.extend(["--active-year", year])
        return self._run_command(cmd, dry_run)

    def _run_scan_references(self, source: Optional[str], year: Optional[str], dry_run: bool) -> dict:
        """Run reference scanning stage."""
        cmd = ["python3", "-m", "reference_scanner", "run"]
        if source:
            cmd.extend(["--source", source])
        if year:
            cmd.extend(["--year", year])
        return self._run_command(cmd, dry_run)


def run_pipeline(
    source: Optional[str] = None,
    year: Optional[str] = None,
    skip_enrich: bool = False,
    dry_run: bool = False
) -> PipelineResult:
    """Convenience function to run the full pipeline."""
    pipeline = CivicPipeline()
    return pipeline.run_full_cycle(
        source=source,
        year=year,
        skip_enrich=skip_enrich,
        dry_run=dry_run
    )


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for pipeline orchestrator."""
    parser = argparse.ArgumentParser(
        description="JaxWatch Pipeline - Run the full data collection and enrichment cycle"
    )
    parser.add_argument("--source", help="Limit to specific source (e.g., 'dia_board')")
    parser.add_argument("--year", help="Limit to specific year")
    parser.add_argument("--skip-enrich", action="store_true",
                        help="Skip AI enrichment stages (verification, references)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without executing")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose logging")

    args = parser.parse_args(argv)

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    print("=" * 60)
    print("JaxWatch Pipeline")
    print("=" * 60)

    result = run_pipeline(
        source=args.source,
        year=args.year,
        skip_enrich=args.skip_enrich,
        dry_run=args.dry_run
    )

    print()
    print(result.summary())

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
