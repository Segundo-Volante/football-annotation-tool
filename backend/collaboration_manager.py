"""Team collaboration management for annotation projects.

Supports multiple collaboration workflows:
- **Solo**: Single annotator, no special handling.
- **Split & Merge**: Divide frames among annotators, merge results.
- **Shared Folder**: Cloud drive (Dropbox, OneDrive, Google Drive) synced folder.
- **Git**: Version-controlled annotations with branching/merging.
- **Custom**: User-defined workflow.

Example team members (for demonstration):
- Jason (lead annotator)
- John Doe
- Jack Smith
- Jane Roe
- Jane Smith
"""

import json
import logging
import math
import os
import subprocess
from pathlib import Path
from typing import Optional

from backend.annotation_store import AnnotationStore

logger = logging.getLogger(__name__)


# Collaboration workflow types
WORKFLOW_TYPES = {
    "solo": "Solo — single annotator",
    "split_merge": "Split & Merge — divide frames, merge later",
    "shared_folder": "Shared Folder — cloud drive sync",
    "git": "Git — version-controlled annotations",
    "custom": "Custom — user-defined workflow",
}

# Demo team for UI examples (fake names as requested)
DEMO_TEAM = [
    {"name": "Jason", "role": "lead"},
    {"name": "John Doe", "role": "annotator"},
    {"name": "Jack Smith", "role": "annotator"},
    {"name": "Jane Roe", "role": "reviewer"},
    {"name": "Jane Smith", "role": "annotator"},
]


class CollaborationManager:
    """Manage team collaboration workflows for annotation projects."""

    def __init__(self, store: AnnotationStore, project_root: str | Path):
        self.store = store
        self.project_root = Path(project_root)
        self._workflow: str = "solo"
        self._annotator: str = ""
        self._team: list[dict] = []

    @property
    def workflow(self) -> str:
        return self._workflow

    @workflow.setter
    def workflow(self, value: str):
        if value not in WORKFLOW_TYPES:
            raise ValueError(f"Unknown workflow: {value}")
        self._workflow = value

    @property
    def annotator(self) -> str:
        return self._annotator

    @annotator.setter
    def annotator(self, value: str):
        self._annotator = value

    @property
    def team(self) -> list[dict]:
        return self._team

    @team.setter
    def team(self, value: list[dict]):
        self._team = value

    # ── Split & Merge ──

    def split_frames(self, filenames: list[str],
                     annotators: list[str],
                     strategy: str = "round_robin") -> dict:
        """Divide frames among annotators.

        Args:
            filenames: All frame filenames to distribute.
            annotators: List of annotator names.
            strategy: 'round_robin' or 'contiguous'.

        Returns:
            ``{annotator_name: [filename, ...]}``
        """
        if not annotators:
            raise ValueError("Need at least one annotator")

        assignments = {name: [] for name in annotators}

        if strategy == "round_robin":
            for i, fname in enumerate(filenames):
                annotator = annotators[i % len(annotators)]
                assignments[annotator].append(fname)
        elif strategy == "contiguous":
            chunk_size = math.ceil(len(filenames) / len(annotators))
            for i, name in enumerate(annotators):
                start = i * chunk_size
                end = min(start + chunk_size, len(filenames))
                assignments[name] = filenames[start:end]
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        # Save assignments to a manifest file
        manifest_path = self.project_root / "annotations" / "_assignments.json"
        manifest_path.write_text(
            json.dumps(assignments, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Tag each frame with its assigned annotator
        for annotator_name, fnames in assignments.items():
            for fname in fnames:
                self.store.save_frame_metadata(fname, annotator=annotator_name)

        logger.info("Split %d frames among %d annotators (%s)",
                     len(filenames), len(annotators), strategy)
        return assignments

    def get_assignments(self) -> Optional[dict]:
        """Load existing frame assignments."""
        manifest_path = self.project_root / "annotations" / "_assignments.json"
        if not manifest_path.exists():
            return None
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def get_my_frames(self) -> list[str]:
        """Return filenames assigned to the current annotator."""
        assignments = self.get_assignments()
        if not assignments or not self._annotator:
            return []
        return assignments.get(self._annotator, [])

    def merge_results(self) -> dict:
        """Merge annotations from all annotators.

        In the per-frame JSON architecture, annotations are already
        file-level so merging is essentially a no-op — each annotator
        writes their own frame files.

        Returns a summary of what was merged.
        """
        stats = self.store.get_session_stats()
        assignments = self.get_assignments()

        per_annotator = {}
        if assignments:
            for annotator_name, fnames in assignments.items():
                annotated = 0
                for fname in fnames:
                    frame = self.store.get_frame_annotation(fname)
                    if frame and frame.status == FrameStatus.ANNOTATED:
                        annotated += 1
                per_annotator[annotator_name] = {
                    "assigned": len(fnames),
                    "annotated": annotated,
                }

        return {
            "total_frames": stats["total"],
            "total_annotated": stats["annotated"],
            "per_annotator": per_annotator,
        }

    # ── Claiming (Shared Folder workflow) ──

    def claim_frame(self, filename: str) -> bool:
        """Claim a frame for the current annotator (shared folder workflow).

        Uses a lock file mechanism to prevent conflicts.
        """
        if not self._annotator:
            return False

        lock_dir = self.project_root / "annotations" / ".locks"
        lock_dir.mkdir(exist_ok=True)
        lock_file = lock_dir / f"{Path(filename).stem}.lock"

        if lock_file.exists():
            existing = lock_file.read_text(encoding="utf-8").strip()
            if existing != self._annotator:
                logger.warning("Frame %s already claimed by %s", filename, existing)
                return False
            return True  # Already claimed by us

        lock_file.write_text(self._annotator, encoding="utf-8")
        self.store.save_frame_metadata(filename, annotator=self._annotator)
        return True

    def release_frame(self, filename: str):
        """Release a claimed frame."""
        lock_dir = self.project_root / "annotations" / ".locks"
        lock_file = lock_dir / f"{Path(filename).stem}.lock"
        if lock_file.exists():
            lock_file.unlink()

    def get_claimed_by(self, filename: str) -> Optional[str]:
        """Return the annotator who claimed this frame, or None."""
        lock_dir = self.project_root / "annotations" / ".locks"
        lock_file = lock_dir / f"{Path(filename).stem}.lock"
        if lock_file.exists():
            return lock_file.read_text(encoding="utf-8").strip()
        return None

    # ── Git workflow ──

    def git_status(self) -> Optional[dict]:
        """Get git status of the annotations directory."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "annotations/"],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return None

            lines = [l for l in result.stdout.strip().split("\n") if l]
            modified = [l for l in lines if l.startswith(" M") or l.startswith("M ")]
            added = [l for l in lines if l.startswith("A ") or l.startswith("??")]
            deleted = [l for l in lines if l.startswith(" D") or l.startswith("D ")]

            # Get current branch
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=5,
            )
            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

            return {
                "branch": branch,
                "modified": len(modified),
                "added": len(added),
                "deleted": len(deleted),
                "total_changes": len(lines),
                "clean": len(lines) == 0,
            }
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def git_commit(self, message: str) -> bool:
        """Commit annotation changes."""
        try:
            subprocess.run(
                ["git", "add", "annotations/"],
                cwd=str(self.project_root),
                capture_output=True, timeout=10,
            )
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=15,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def git_pull(self) -> Optional[str]:
        """Pull latest changes."""
        try:
            result = subprocess.run(
                ["git", "pull", "--rebase"],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=30,
            )
            return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def git_push(self) -> Optional[str]:
        """Push annotation commits."""
        try:
            result = subprocess.run(
                ["git", "push"],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=30,
            )
            return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None


# Import FrameStatus for merge_results
from backend.models import FrameStatus
