import argparse
import json


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
    ingest.add_argument("--embedding-mode", choices=("auto", "subprocess", "in-process"), default="auto")
    ingest.add_argument("--visual-batch-size", type=int, default=2)
    extend = commands.add_parser("extend", help="Append one video, reusing completed base FAISS index")
    extend.add_argument("--base-index", required=True)
    extend.add_argument("--manifest", required=True)
    extend.add_argument("--output", required=True)
    extend.add_argument("--device", choices=("cpu", "mps", "cuda"), default=None)
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--index", default="artifacts/index")
    search.add_argument("--mode", choices=("visual", "transcript", "hybrid"), default="hybrid")
    search.add_argument("--k", type=int, default=5)
    search.add_argument("--offline", action="store_true",
                        help="Use cached Hugging Face models only; never access the Hub")
    search.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="auto")
    search.add_argument("--embedding-mode", choices=("auto", "subprocess", "in-process"), default="auto")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--index", default="artifacts/index")
    evaluate.add_argument("--labels", default="evaluation/labels.json")
    evaluate.add_argument("--output", required=True)
    evaluate.add_argument("--split", choices=("dev", "test"), default="test")
    evaluate.add_argument("--k", type=int, default=5)
    evaluate.add_argument("--plan", help="Frozen plan required for finalized human-review labels")
    evaluate.add_argument("--compare-equal-rrf", action="store_true",
                          help="Add an equal-weight RRF ablation without changing search behavior")
    evaluate.add_argument("--offline", action="store_true",
                          help="Use cached Hugging Face models only; never access the Hub")
    evaluate.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="auto")
    evaluate.add_argument("--embedding-mode", choices=("auto", "subprocess", "in-process"), default="auto")
    labels = commands.add_parser("init-labels", help="Create a blank annotation form without loading models")
    labels.add_argument("--index", default="artifacts/index")
    labels.add_argument("--output", default="evaluation/labels.json")
    labels.add_argument("--count", type=int, default=24)
    labels.add_argument("--dev-count", type=int, default=6)
    freeze = commands.add_parser("freeze-labels", help="Record queries and splits before labeling or ranking")
    freeze.add_argument("--index", required=True)
    freeze.add_argument("--labels", required=True)
    freeze.add_argument("--output", required=True)
    freeze.add_argument("--exclude-labels", action="append", default=[],
                        help="Reject exact normalized reuse of old query text; repeat for multiple files")
    finalize = commands.add_parser("finalize-labels", help="Validate per-query human-review records")
    finalize.add_argument("--index", required=True)
    finalize.add_argument("--labels", required=True)
    finalize.add_argument("--plan", required=True)
    finalize.add_argument("--output", required=True)
    args = parser.parse_args()
    if getattr(args, "offline", False):
        # Set before importing either model library; isolated workers inherit it.
        from .query_worker import enable_offline_cache
        enable_offline_cache()
    try:
        if args.command == "ingest":
            from .pipeline import build
            result = build(args.manifest, args.output, args.whisper_model, args.language,
                           args.frame_seconds, args.window_seconds, args.device,
                           args.embedding_mode, args.visual_batch_size)
        elif args.command == "extend":
            from .extend import extend as extend_index
            result = extend_index(args.base_index, args.manifest, args.output, device=args.device)
        elif args.command == "init-labels":
            from .annotations import init_labels
            result = init_labels(args.index, args.output, args.count, args.dev_count)
        elif args.command == "freeze-labels":
            from .annotations import freeze_labels
            result = freeze_labels(args.index, args.labels, args.output, args.exclude_labels)
        elif args.command == "finalize-labels":
            from .annotations import finalize_labels
            result = finalize_labels(args.index, args.labels, args.plan, args.output)
        else:
            from .search import SearchEngine
            engine = SearchEngine(args.index, device=args.device, embedding_mode=args.embedding_mode)
            if args.command == "search":
                result = engine.search(args.query, args.mode, args.k)
            else:
                from .evaluate import evaluate as run_evaluation
                result = run_evaluation(engine, args.labels, args.output, args.split, args.k,
                                        plan_path=args.plan, compare_equal_rrf=args.compare_equal_rrf)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, ImportError, RuntimeError) as e:
        parser.exit(2, f"Error: {e}\n")


if __name__ == "__main__":
    main()
