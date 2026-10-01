from __future__ import annotations

import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from . import __version__
from .diagnostics import reject_unsafe_codex_input


@dataclass
class DoctorReport:
    version: str
    python: str
    executable: str
    package_source: str
    git_root: str
    git_commit: str
    git_branch: str
    working_tree: str
    repository_match: str
    privacy_guard: str


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False, capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _find_git_root(source: Path) -> Path | None:
    current = source.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def doctor() -> DoctorReport:
    source = Path(__file__).resolve()
    root = _find_git_root(source)
    commit = branch = ""
    tree = "not-a-git-checkout"
    repo_match = "UNKNOWN"
    if root:
        commit = _git(root, "rev-parse", "--short", "HEAD")
        branch = _git(root, "branch", "--show-current")
        tree = "clean" if not _git(root, "status", "--porcelain") else "dirty"
        # Editable installs should resolve into the current checkout. A package imported
        # elsewhere is a common cause of users running an older CLI than the repository.
        try:
            source.relative_to(root)
            repo_match = "PASS"
        except ValueError:
            repo_match = "MISMATCH"
    guard = "PASS"
    try:
        reject_unsafe_codex_input(Path("/synthetic/CODEX_SAFE/corpus_summary.json"))
    except ValueError:
        guard = "FAIL"
    return DoctorReport(
        version=__version__,
        python=sys.version.split()[0],
        executable=sys.executable,
        package_source=str(source),
        git_root=str(root or ""),
        git_commit=commit,
        git_branch=branch,
        working_tree=tree,
        repository_match=repo_match,
        privacy_guard=guard,
    )


def doctor_rows() -> list[tuple[str, str]]:
    report = asdict(doctor())
    labels = {
        "version": "ClaimLens version",
        "python": "Python",
        "executable": "Python executable",
        "package_source": "Package source",
        "git_root": "Git root",
        "git_commit": "Git commit",
        "git_branch": "Git branch",
        "working_tree": "Working tree",
        "repository_match": "Repository/source",
        "privacy_guard": "Privacy guard",
    }
    return [(labels[key], str(value)) for key, value in report.items()]
