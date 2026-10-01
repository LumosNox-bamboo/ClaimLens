from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .batch import run_batch
from .claims import extract_claims
from .exporters import export_claims
from .identity import ensure_salt
from .identity import candidate_id as make_candidate_id
from .models import PrivacyMode
from .parsers import PARSERS, embedded_image_count, extract_text
from .privacy import pii_summary, redact_text
from .review import build_review, review_summary

DEFAULT_SALT = Path(".claimlens/project.salt")


def _files(path: Path):
    if path.is_file():
        yield path
    else:
        for item in sorted(path.iterdir()):
            if item.is_file() and item.suffix.lower() in PARSERS:
                yield item


def cmd_extract(args: argparse.Namespace) -> int:
    salt = ensure_salt(args.salt_file)
    all_claims = []
    privacy_manifest = []
    for path in _files(args.input):
        try:
            text = extract_text(path)
            cid = make_candidate_id(path, salt)
            _, findings = redact_text(text, args.privacy)
            claims = extract_claims(text, cid, path.suffix)
            all_claims.extend(claims)
            image_count = embedded_image_count(path)
            privacy_manifest.append({"candidate_id": cid, "source_type": path.suffix.lower(), "pii_detected": pii_summary(findings), "embedded_images": image_count, "image_warning": bool(image_count), "claims": len(claims)})
            if image_count:
                print(f"privacy warning {cid}: source document contains embedded image(s); images are not verifier inputs")
            print(f"processed {cid}: {len(claims)} claim(s)")
        except Exception as exc:
            print(f"error processing one {path.suffix.lower()} document: {exc}", file=sys.stderr)
    paths = export_claims(all_claims, args.out)
    (args.out / "privacy_manifest.json").write_text(json.dumps(privacy_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    build_review(paths[0], args.out / "privacy_review.json")
    print(f"wrote {len(all_claims)} claim(s) to {args.out}; no network access performed")
    print(f"local visual review: {args.out / 'claims_review.html'}")
    return 0


def cmd_redact(args: argparse.Namespace) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    for path in _files(args.input):
        text = extract_text(path)
        redacted, findings = redact_text(text, args.privacy, keep=args.keep, remove=args.remove)
        cid = make_candidate_id(path, ensure_salt(args.salt_file))
        (args.out / f"{cid}.redacted.txt").write_text(redacted, encoding="utf-8")
        print(f"redacted {cid}: {sum(pii_summary(findings).values())} potential PII span(s)")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    path = args.path / "privacy_review.json" if args.path.is_dir() else args.path
    total, approved = review_summary(path)
    print(f"Privacy Review: {approved}/{total} approved for future network verification")
    print(f"Edit {path} locally and inspect outbound_fields before approving any item.")
    print("No data has been sent over the network.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    path = args.path / "privacy_review.json" if args.path.is_dir() else args.path
    total, approved = review_summary(path)
    if not total or approved != total:
        print("Verification blocked: Privacy Review approval is required for every outbound item.", file=sys.stderr)
        return 2
    print("P0 has no network verification providers enabled; approved review recorded locally.")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    salt = ensure_salt(args.salt_file)
    candidates, claims, failures = run_batch(
        args.input, args.out, salt, args.privacy, args.filename
    )
    print(
        f"batch complete: {candidates} candidate(s), {claims} claim(s), "
        f"{failures} failure(s); no network access performed"
    )
    print(f"LOCAL ONLY identity map: {args.out / '00_LOCAL_ONLY' / 'candidate_map.xlsx'}")
    print(f"Codex-ready redacted package: {args.out / '01_CODEX_READY'}")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="claimlens", description="Privacy-first, local-first CV claim verification toolkit")
    sub = p.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("input", type=Path)
    common.add_argument("--out", type=Path, default=Path("review"))
    common.add_argument("--privacy", choices=[x.value for x in PrivacyMode], default="verification")
    common.add_argument("--salt-file", type=Path, default=DEFAULT_SALT, help="Local HMAC salt file (never commit it)")
    ex = sub.add_parser("extract", parents=[common])
    ex.set_defaults(func=cmd_extract)
    rd = sub.add_parser("redact", parents=[common])
    rd.add_argument("--keep", action="append", default=[])
    rd.add_argument("--remove", action="append", default=[])
    rd.set_defaults(func=cmd_redact)
    rv = sub.add_parser("review")
    rv.add_argument("path", type=Path)
    rv.set_defaults(func=cmd_review)
    vf = sub.add_parser("verify")
    vf.add_argument("path", type=Path)
    vf.set_defaults(func=cmd_verify)
    bt = sub.add_parser("batch", parents=[common])
    bt.add_argument(
        "--filename", default="简历.pdf",
        help="CV filename to discover recursively (default: 简历.pdf)",
    )
    bt.set_defaults(func=cmd_batch)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
