from pathlib import Path
from claimlens.parsers import extract_text


def test_txt_parser(tmp_path: Path):
    p = tmp_path / "synthetic.txt"
    p.write_text("虚构简历 Synthetic CV", encoding="utf-8")
    assert "Synthetic CV" in extract_text(p)


def test_txt_has_no_embedded_images(tmp_path: Path):
    from claimlens.parsers import embedded_image_count
    p = tmp_path / "synthetic.txt"
    p.write_text("synthetic", encoding="utf-8")
    assert embedded_image_count(p) == 0
