from pathlib import Path

import pytest

from claimlens.diagnostics import reject_unsafe_codex_input
from claimlens.health import doctor


def test_doctor_reports_package_and_privacy_guard():
    report = doctor()
    assert report.version
    assert report.python
    assert report.package_source.endswith("claimlens/health.py")
    assert report.privacy_guard == "PASS"


@pytest.mark.parametrize(
    "path",
    [
        "/project/resumes/candidate/cv.pdf",
        "/project/00_LOCAL_ONLY/candidate_map.xlsx",
        "/project/01_EXTRACTION_DIAGNOSTICS/LOCAL_ONLY/C-SYNTH.extraction.json",
        "/tmp/cv.docx",
    ],
)
def test_privacy_check_blocks_unsafe_inputs(path):
    with pytest.raises(ValueError):
        reject_unsafe_codex_input(Path(path))


def test_privacy_check_accepts_codex_safe_summary():
    reject_unsafe_codex_input(
        Path("/project/01_EXTRACTION_DIAGNOSTICS/CODEX_SAFE/corpus_summary.json")
    )
