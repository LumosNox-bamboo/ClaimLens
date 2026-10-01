from pathlib import Path
from claimlens.identity import candidate_id


def test_candidate_id_is_stable_and_keyed(tmp_path: Path):
    p = tmp_path / "cv.txt"
    p.write_text("synthetic cv", encoding="utf-8")
    a = candidate_id(p, b"a" * 32)
    b = candidate_id(p, b"b" * 32)
    assert a == candidate_id(p, b"a" * 32)
    assert a.startswith("C-") and len(a) == 8 and a != b
