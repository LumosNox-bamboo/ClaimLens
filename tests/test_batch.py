from pathlib import Path

from claimlens.batch import discover_cvs, parse_candidate_folder


def test_parse_scientific_forum_folder():
    kind, app_id, name = parse_candidate_folder(
        "either_博士后_SCDSG26-A-ABC123_示例候选人"
    )
    assert kind == "either_博士后"
    assert app_id == "SCDSG26-A-ABC123"
    assert name == "示例候选人"


def test_discover_only_requested_cv_filename(tmp_path: Path):
    a = tmp_path / "candidate_a"
    b = tmp_path / "candidate_b"
    a.mkdir()
    b.mkdir()
    (a / "简历.pdf").write_bytes(b"synthetic")
    (a / "other.pdf").write_bytes(b"synthetic")
    (b / "简历.pdf").write_bytes(b"synthetic")
    assert discover_cvs(tmp_path) == [a / "简历.pdf", b / "简历.pdf"]
