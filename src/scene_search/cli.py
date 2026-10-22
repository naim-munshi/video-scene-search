import argparse
import json
from pathlib import Path

from .core import read_json, sha256, write_json


def main():
    parser = argparse.ArgumentParser(description="Local video scene search")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Transcribe, sample frames, embed and index")
    ingest.add_argument("--manifest", required=True)
    ingest.add_argument("--output", default="artifacts/index")
    ingest.add_argument("--whisper-model", default="base")
    ingest.add_argument("--language", default=None, help="en, ja, bn, etc.; default auto-detect")
    ingest.add_argument("--frame-seconds", type=float, default=2)
    ingest.add_argument("--window-seconds", type=float, default=10)
    ingest.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--index", default="artifacts/index")
    search.add_argument("--mode", choices=("visual", "transcript", "hybrid"), default="hybrid")
    search.add_argument("--k", type=int, default=5)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--index", default="artifacts/index")
    evaluate.add_argument("--labels", default="evaluation/labels.json")
    evaluate.add_argument("--output", required=True)
    evaluate.add_argument("--split", choices=("dev", "test"), default="test")
    evaluate.add_argument("--k", type=int, default=5)
    labels = commands.add_parser("init-labels", help="Create a blank 24-query annotation form")
    labels.add_argument("--index", default="artifacts/index")
    labels.add_argument("--output", default="evaluation/labels.json")
    args = parser.parse_args()
    try:
        if args.command == "ingest":
            from .pipeline import build
            result = build(args.manifest, args.output, args.whisper_model, args.language,
                           args.frame_seconds, args.window_seconds, args.device)
        elif args.command == "init-labels":
            if Path(args.output).exists():
                raise ValueError("Labels already exist; refusing to overwrite")
            root = Path(args.index)
            read_json(root / "windows.json")
            write_json(args.output, {"status": "draft", "build_sha256": sha256(root / "build.json"),
                "queries": [{"id": f"q{i+1:02d}", "text": "", "kind": ("visual", "speech", "mixed")[i % 3],
                             "split": "dev" if i < 6 else "test", "relevant": []} for i in range(24)]})
            result = {"labels": args.output, "instructions": "Write queries and hand-label relevant window IDs using the Annotate tab"}
        else:
            from .search import SearchEngine
            engine = SearchEngine(args.index)
            if args.command == "search":
                result = engine.search(args.query, args.mode, args.k)
            else:
                from .evaluate import evaluate as run_evaluation
                result = run_evaluation(engine, args.labels, args.output, args.split, args.k)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, ImportError, RuntimeError) as e:
        parser.exit(2, f"Error: {e}\n")


if __name__ == "__main__":
    main()
