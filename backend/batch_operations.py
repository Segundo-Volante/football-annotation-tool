"""Batch operations for annotation data.

Provides bulk search, filter, edit, and delete across multiple frames
for efficient annotation review and correction.
"""

import logging
from typing import Optional

from backend.annotation_store import AnnotationStore
from backend.models import (
    BoundingBox, Category, CATEGORY_NAMES, FrameAnnotation, FrameStatus,
    Occlusion,
)

logger = logging.getLogger(__name__)


class BatchOperations:
    """Batch search, filter, and edit operations across frames."""

    def __init__(self, store: AnnotationStore):
        self.store = store

    # ── Search & Filter ──

    def search_by_jersey(self, jersey_number: int) -> list[dict]:
        """Find all frames containing a specific jersey number.

        Returns list of ``{filename, box_count, player_name}``.
        """
        results = []
        for frame in self.store.iter_all_frames():
            matching_boxes = [
                b for b in frame.boxes
                if b.jersey_number == jersey_number
            ]
            if matching_boxes:
                names = [b.player_name for b in matching_boxes if b.player_name]
                results.append({
                    "filename": frame.original_filename,
                    "box_count": len(matching_boxes),
                    "player_name": names[0] if names else None,
                    "status": frame.status.value,
                })
        return results

    def search_by_player_name(self, name: str) -> list[dict]:
        """Find all frames containing a player name (case-insensitive partial match)."""
        results = []
        name_lower = name.lower()
        for frame in self.store.iter_all_frames():
            matching = [
                b for b in frame.boxes
                if b.player_name and name_lower in b.player_name.lower()
            ]
            if matching:
                results.append({
                    "filename": frame.original_filename,
                    "box_count": len(matching),
                    "jerseys": [b.jersey_number for b in matching if b.jersey_number is not None],
                    "status": frame.status.value,
                })
        return results

    def filter_by_category(self, category: Category) -> list[dict]:
        """Find all frames containing boxes of a specific category."""
        results = []
        for frame in self.store.iter_all_frames():
            matching = [b for b in frame.boxes if b.category == category]
            if matching:
                results.append({
                    "filename": frame.original_filename,
                    "box_count": len(matching),
                    "status": frame.status.value,
                })
        return results

    def filter_by_status(self, status: FrameStatus) -> list[dict]:
        """Find all frames with a given status."""
        results = []
        for frame in self.store.iter_all_frames():
            if frame.status == status:
                results.append({
                    "filename": frame.original_filename,
                    "box_count": len(frame.boxes),
                    "status": frame.status.value,
                })
        return results

    def filter_frames_with_issues(self) -> list[dict]:
        """Find frames with potential annotation issues."""
        results = []
        for frame in self.store.iter_all_frames():
            issues = []

            # Annotated with no boxes
            if frame.status == FrameStatus.ANNOTATED and not frame.boxes:
                issues.append("No boxes")

            # Pending AI boxes
            pending = [b for b in frame.boxes if b.box_status.value == "pending"]
            if pending:
                issues.append(f"{len(pending)} pending")

            # Very small boxes
            tiny = [b for b in frame.boxes if b.width < 10 or b.height < 10]
            if tiny:
                issues.append(f"{len(tiny)} tiny boxes")

            if issues:
                results.append({
                    "filename": frame.original_filename,
                    "issues": issues,
                    "box_count": len(frame.boxes),
                    "status": frame.status.value,
                })
        return results

    # ── Bulk Edit ──

    def bulk_change_jersey(self, old_jersey: int, new_jersey: int,
                           new_name: Optional[str] = None,
                           category_filter: Optional[Category] = None) -> int:
        """Change jersey number across all frames.

        Args:
            old_jersey: Current jersey number to find.
            new_jersey: New jersey number to assign.
            new_name: Optionally update the player name too.
            category_filter: Only change for this category.

        Returns:
            Number of boxes updated.
        """
        count = 0
        for frame in self.store.iter_all_frames():
            for box in frame.boxes:
                if box.jersey_number != old_jersey:
                    continue
                if category_filter and box.category != category_filter:
                    continue

                updates = {"jersey_number": new_jersey}
                if new_name is not None:
                    updates["player_name"] = new_name
                self.store.update_box(
                    frame.original_filename, box.id, **updates
                )
                count += 1
        return count

    def bulk_change_category(self, filename: str,
                             from_category: Category,
                             to_category: Category) -> int:
        """Change all boxes of one category to another in a single frame."""
        count = 0
        frame = self.store.get_frame_annotation(filename)
        if not frame:
            return 0
        for box in frame.boxes:
            if box.category == from_category:
                self.store.update_box(filename, box.id, category=to_category)
                count += 1
        return count

    def bulk_delete_by_category(self, filename: str,
                                category: Category) -> int:
        """Delete all boxes of a specific category in a frame."""
        count = 0
        frame = self.store.get_frame_annotation(filename)
        if not frame:
            return 0
        for box in frame.boxes:
            if box.category == category:
                self.store.delete_box(filename, box.id)
                count += 1
        return count

    def bulk_reset_frames(self, filenames: list[str]) -> int:
        """Reset frames back to unviewed status (keep annotations)."""
        count = 0
        for filename in filenames:
            self.store.set_frame_status(filename, FrameStatus.UNVIEWED)
            count += 1
        return count

    def bulk_delete_all_boxes(self, filename: str) -> int:
        """Delete all boxes in a frame."""
        frame = self.store.get_frame_annotation(filename)
        if not frame:
            return 0
        count = len(frame.boxes)
        for box in frame.boxes:
            self.store.delete_box(filename, box.id)
        return count

    # ── Statistics ──

    def get_player_summary(self) -> list[dict]:
        """Get summary of all players seen across the dataset.

        Returns list of ``{jersey, name, category, appearances}``.
        """
        players = {}  # (jersey, name, category) -> count

        for frame in self.store.iter_all_frames():
            for box in frame.boxes:
                if box.jersey_number is None:
                    continue
                key = (
                    box.jersey_number,
                    box.player_name or "Unknown",
                    CATEGORY_NAMES.get(box.category, "unknown"),
                )
                players[key] = players.get(key, 0) + 1

        result = []
        for (jersey, name, cat), count in sorted(players.items()):
            result.append({
                "jersey": jersey,
                "name": name,
                "category": cat,
                "appearances": count,
            })
        return result
