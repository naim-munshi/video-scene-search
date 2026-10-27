"""Seed 24 candidate real-video evaluation queries, never ground-truth labels.

The suggestions must be checked against the *actual* source footage before
use. This script does not inspect search results or invent window IDs.
It will not overwrite the existing JSON or any existing annotation.

Usage:
  python scripts/seed_portfolio_queries.py
  python scripts/seed_portfolio_queries.py --dry-run
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scene_search.core import read_json, sha256, write_json

# q01-q06 are development; q07-q24 are blind held-out test suggestions.
# Candidate queries are hypothetical until a human reviews the recordings.
# Order: 2 dev per video; then 6 test per video.
QUERIES = (
    ("q01", "portfolio_nasa", "A person describes a lunar or space mission.", "speech"),
    ("q02", "portfolio_nasa", "A man sits beside scientific equipment.", "visual"),
    ("q03", "portfolio_interview", "An older man in a dark shirt speaking in an interview.", "visual"),
    ("q04", "portfolio_interview", "An interviewee answers a question about technology.", "speech"),
    ("q05", "portfolio_film", "A futuristic machine or structure is shown.", "visual"),
    ("q06", "portfolio_film", "A character speaks during a science fiction scene.", "mixed"),
    ("q07", "portfolio_interview", "A close-up of the interviewee's face.", "visual"),
    ("q08", "portfolio_interview", "The guest speaks about computers.", "speech"),
    ("q09", "portfolio_interview", "The interviewee explains an idea while on camera.", "mixed"),
    ("q10", "portfolio_interview", "An interview shot shows the speaker seated.", "visual"),
    ("q11", "portfolio_interview", "Someone mentions engineering or electronics.", "speech"),
    ("q12", "portfolio_interview", "The guest speaks while making a hand gesture.", "mixed"),
    ("q13", "portfolio_film", "Two people appear together in a live-action shot.", "visual"),
    ("q14", "portfolio_film", "A futuristic vehicle or mechanical object appears.", "visual"),
    ("q15", "portfolio_film", "One character speaks to another character.", "speech"),
    ("q16", "portfolio_film", "A conversation takes place inside a building.", "mixed"),
    ("q17", "portfolio_film", "A scene contains computer-generated visual effects.", "visual"),
    ("q18", "portfolio_film", "Someone talks while futuristic machinery is visible.", "mixed"),
    ("q19", "portfolio_nasa", "Aerospace machinery is visible in archival footage.", "visual"),
    ("q20", "portfolio_nasa", "A narrator talks about a space mission.", "speech"),
    ("q21", "portfolio_nasa", "A man speaks while scientific equipment is visible.", "mixed"),
    ("q22", "portfolio_nasa", "A close-up of a person appears in the NASA footage.", "visual"),
    ("q23", "portfolio_nasa", "A speaker discusses travel or a mission.", "speech"),
    ("q24", "portfolio_nasa", "Archival space-program footage accompanies spoken explanation.", "mixed"),
)


def seed_queries(index, source, output):
    index = Path(index).expanduser().resolve()
    source = Path(source).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    if output.exists() or source == output:
        raise ValueError("Refusing to overwrite a labels file")
    meta = read_json(index / "corpus.json")
    allowed = {v["id"] for v in meta["videos"]}
    expected = {"portfolio_interview", "portfolio_film", "portfolio_nasa"}
    if allowed != expected:
        raise ValueError("The target index must contain exactly the three portfolio videos")
    original = read_json(source)
    if original.get("status") != "draft":
        raise ValueError("Refusing to alter reviewed/annotated labels")
    if original.get("build_sha256") != sha256(index / "build.json"):
        raise ValueError("The labels JSON does not match the index build")
    current = original.get("queries")
    if not isinstance(current, list) or len(current) != len(QUERIES):
        raise ValueError("Expected the existing 24-query draft template")
    expected_ids = {r[0] for r in QUERIES}
    by_id = {r.get("id"): dict(r) for r in current if isinstance(r, dict)}
    if len(by_id) != len(QUERIES) or set(by_id) != expected_ids:
        raise ValueError("Template must have exactly q01–q24 with unique IDs")
    for i, (qid, target, proposed_text, kind) in enumerate(QUERIES):
        split = "dev" if i < 6 else "test"
        row = by_id[qid]
        if row.get("split") != split:
            raise ValueError(f"Unexpected split in {qid}; refusing to rewrite")
        if target not in allowed:
            raise ValueError(f"Target video is missing: {target}")
        if not isinstance(row.get("relevant"), list):
            raise ValueError(f"Invalid relevant window list in {qid}")
        # Only seed empty text; preserve all prior human annotations unchanged.
        if not str(row.get("text", "")).strip():
            row["text"] = proposed_text
            row["kind"] = kind
        by_id[qid] = row
    result = {**original, "status": "draft",
              "queries": [by_id[qid] for qid, *_ in QUERIES]}
    write_json(output, result)
    return {"path": str(output),
            "queries": len(result["queries"]), "dev": 6, "test": 18,
            "human_labeled": sum(bool(q["relevant"]) for q in result["queries"]),
            "notice": "All candidate queries require human video review. No relevance labels invented."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="artifacts/portfolio-real-v2")
    parser.add_argument("--source", default="evaluation/portfolio-real-v2-labels.json")
    parser.add_argument("--output", default="evaluation/portfolio-real-v2-query-draft.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.dry_run:
            for index, (qid, video, query, kind) in enumerate(QUERIES):
                print(f"{qid} | {'dev' if index < 6 else 'test'} | "
                      f"{video} | {kind} | {query}")
        else:
            print(json.dumps(seed_queries(args.index, args.source, args.output),
                             ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Cannot seed evaluation queries: {exc}\n")


if __name__ == "__main__":
    main()
