"""Dataset health analysis for annotation quality assurance.

Scans all annotations to detect potential issues, generate distribution
statistics, and provide actionable insights via the Health Dashboard.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Optional

from backend.annotation_store import AnnotationStore
from backend.models import (
    Category, CATEGORY_NAMES, FrameStatus, Occlusion,
)


class HealthAnalyzer:
    """Analyzes annotation data for quality and completeness issues."""

    def __init__(self, store: AnnotationStore):
        self.store = store

    def run_full_analysis(self) -> dict:
        """Run complete health analysis. Returns a structured report."""
        frames = list(self.store.iter_all_frames())

        report = {
            "frame_stats": self._frame_stats(frames),
            "box_stats": self._box_stats(frames),
            "category_distribution": self._category_distribution(frames),
            "jersey_distribution": self._jersey_distribution(frames),
            "occlusion_distribution": self._occlusion_distribution(frames),
            "issues": self._detect_issues(frames),
            "metadata_coverage": self._metadata_coverage(frames),
        }
        return report

    def _frame_stats(self, frames: list) -> dict:
        status_counts = Counter()
        total_boxes = 0
        frames_with_boxes = 0
        box_counts = []

        for frame in frames:
            status_counts[frame.status.value] += 1
            n_boxes = len(frame.boxes)
            total_boxes += n_boxes
            box_counts.append(n_boxes)
            if n_boxes > 0:
                frames_with_boxes += 1

        return {
            "total_frames": len(frames),
            "by_status": dict(status_counts),
            "total_boxes": total_boxes,
            "frames_with_boxes": frames_with_boxes,
            "avg_boxes_per_frame": round(total_boxes / max(len(frames), 1), 1),
            "max_boxes_in_frame": max(box_counts) if box_counts else 0,
            "min_boxes_in_frame": min(box_counts) if box_counts else 0,
        }

    def _box_stats(self, frames: list) -> dict:
        total = 0
        manual = 0
        ai = 0
        pending = 0
        finalized = 0
        truncated = 0

        for frame in frames:
            for box in frame.boxes:
                total += 1
                if box.source.value == "manual":
                    manual += 1
                else:
                    ai += 1
                if box.box_status.value == "pending":
                    pending += 1
                else:
                    finalized += 1
                if box.truncated:
                    truncated += 1

        return {
            "total": total,
            "manual": manual,
            "ai_detected": ai,
            "pending": pending,
            "finalized": finalized,
            "truncated": truncated,
        }

    def _category_distribution(self, frames: list) -> dict:
        counts = Counter()
        for frame in frames:
            for box in frame.boxes:
                cat_name = CATEGORY_NAMES.get(box.category, "unknown")
                counts[cat_name] += 1
        return dict(counts)

    def _jersey_distribution(self, frames: list) -> dict:
        jerseys = Counter()
        for frame in frames:
            for box in frame.boxes:
                if box.jersey_number is not None:
                    key = f"#{box.jersey_number}"
                    if box.player_name:
                        key += f" {box.player_name}"
                    jerseys[key] += 1
        # Return sorted by count descending
        return dict(jerseys.most_common(50))

    def _occlusion_distribution(self, frames: list) -> dict:
        counts = Counter()
        for frame in frames:
            for box in frame.boxes:
                counts[box.occlusion.value] += 1
        return dict(counts)

    def _metadata_coverage(self, frames: list) -> dict:
        """Check how many annotated frames have complete metadata."""
        annotated = [f for f in frames if f.status == FrameStatus.ANNOTATED]
        if not annotated:
            return {"annotated_frames": 0, "coverage": {}}

        # Collect all metadata keys seen
        all_keys = set()
        for frame in annotated:
            all_keys.update(frame.metadata.keys())

        coverage = {}
        for key in sorted(all_keys):
            filled = sum(1 for f in annotated if f.metadata.get(key))
            coverage[key] = {
                "filled": filled,
                "total": len(annotated),
                "percent": round(filled / len(annotated) * 100, 1),
            }

        return {
            "annotated_frames": len(annotated),
            "coverage": coverage,
        }

    def _detect_issues(self, frames: list) -> list[dict]:
        """Detect potential quality issues."""
        issues = []

        for frame in frames:
            # Issue: Annotated frame with zero boxes
            if frame.status == FrameStatus.ANNOTATED and len(frame.boxes) == 0:
                issues.append({
                    "type": "empty_annotated",
                    "severity": "warning",
                    "frame": frame.original_filename,
                    "message": "Annotated frame has no bounding boxes",
                })

            # Issue: Frame with pending boxes
            pending = [b for b in frame.boxes if b.box_status.value == "pending"]
            if pending:
                issues.append({
                    "type": "pending_boxes",
                    "severity": "info",
                    "frame": frame.original_filename,
                    "message": f"{len(pending)} unresolved pending box(es)",
                })

            # Issue: Very small boxes (likely errors)
            for box in frame.boxes:
                if box.width < 10 or box.height < 10:
                    issues.append({
                        "type": "tiny_box",
                        "severity": "warning",
                        "frame": frame.original_filename,
                        "message": f"Very small box ({box.width}x{box.height}px) — "
                                   f"possible error",
                    })

                # Issue: Box outside image bounds
                if frame.image_width > 0 and frame.image_height > 0:
                    if (box.x < 0 or box.y < 0
                            or box.x + box.width > frame.image_width + 5
                            or box.y + box.height > frame.image_height + 5):
                        issues.append({
                            "type": "out_of_bounds",
                            "severity": "warning",
                            "frame": frame.original_filename,
                            "message": "Box extends outside image boundaries",
                        })

            # Issue: Duplicate jersey numbers in same frame for home players
            home_jerseys = [
                b.jersey_number for b in frame.boxes
                if b.category in (Category.HOME_PLAYER, Category.HOME_GK)
                and b.jersey_number is not None
            ]
            dupes = [n for n in set(home_jerseys) if home_jerseys.count(n) > 1]
            for n in dupes:
                issues.append({
                    "type": "duplicate_jersey",
                    "severity": "warning",
                    "frame": frame.original_filename,
                    "message": f"Duplicate home jersey #{n}",
                })

        return issues

    def get_issue_summary(self) -> dict:
        """Return aggregated issue counts by type and severity."""
        report = self.run_full_analysis()
        issues = report["issues"]

        by_type = Counter(i["type"] for i in issues)
        by_severity = Counter(i["severity"] for i in issues)

        return {
            "total_issues": len(issues),
            "by_type": dict(by_type),
            "by_severity": dict(by_severity),
        }
