import json

import pytest

from claimlens.diagnostics import (
    assert_codex_safe,
    build_codex_safe_diagnostics,
    reject_unsafe_codex_input,
)


def synthetic_local_payload():
    return {
        "candidate_id": "C-SYNTH",
        "claims_accepted": 4,
        "items_review": 2,
        "items_dropped": 1,
        "health_flags": ["EXTRACTION_REVIEW_REQUIRED"],
        "ready_for_verification": False,
        "diagnostics": [
            {
                "section": "publications",
                "claim_type": "publication",
                "action": "REVIEW",
                "reasons": ["ORPHAN_FRAGMENT"],
                "preview": "Synthetic Author. Synthetic private title.",
            },
            {
                "section": "patents",
                "claim_type": "patent",
                "action": "REVIEW",
                "reasons": ["PATENT_WITHOUT_IDENTIFIER"],
                "preview": "Synthetic confidential invention.",
            },
        ],
    }


def test_codex_safe_removes_content_and_identity():
    safe = build_codex_safe_diagnostics([synthetic_local_payload()])
    blob = json.dumps(safe, ensure_ascii=False)
    assert "C-SYNTH" not in blob
    assert "Synthetic Author" not in blob
    assert "private title" not in blob
    assert "confidential invention" not in blob
    assert safe["documents"][0]["document"] == "DOC-0001"
    assert safe["failure_patterns"]["reasons"]["ORPHAN_FRAGMENT"] == 1
    assert_codex_safe(safe)


def test_codex_safe_guard_rejects_content_keys():
    with pytest.raises(ValueError):
        assert_codex_safe({"documents": [{"title": "must not leave local boundary"}]})


@pytest.mark.parametrize(
    "unsafe",
    [
        "/project/resumes/person/简历.pdf",
        "/project/batch/00_LOCAL_ONLY/candidate_map.xlsx",
        "/project/batch/LOCAL_ONLY/details.json",
        "/tmp/random.docx",
    ],
)
def test_external_agent_guard_rejects_raw_or_identity_paths(unsafe):
    from pathlib import Path
    with pytest.raises(ValueError):
        reject_unsafe_codex_input(Path(unsafe))


def test_external_agent_guard_accepts_only_codex_safe():
    from pathlib import Path
    reject_unsafe_codex_input(Path("/project/01_EXTRACTION_DIAGNOSTICS/CODEX_SAFE/corpus_summary.json"))
