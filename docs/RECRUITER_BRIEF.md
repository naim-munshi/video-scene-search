# Video Scene Search engineering brief

**Goal:** retrieve a relevant moment from video using visual and spoken evidence,
then let the user inspect its timestamp, thumbnail and transcript. This is a
local single-user engineering prototype, not an ABEMA product or a production
deployment.

## What to review

| Engineering decision | Implementation and trade-off |
| --- | --- |
| Two retrieval channels | CLIP visual embeddings and Whisper ASR plus MiniLM text embeddings cover different evidence; neither guarantees relevance |
| Rank fusion | RRF avoids adding incompatible cosine scores; English query-intent weights are heuristics, now testable against equal-weight RRF |
| Timestamp windows | Fixed 10-second windows simplify indexing/evaluation but can split a semantic scene |
| Local index integrity | Build manifests and hashes identify artifacts; private videos and indexes stay outside Git |
| macOS inference boundary | Isolated query workers contain native model crashes, at the cost of startup overhead |
| Evaluation discipline | Freeze queries/splits, record per-query human review, compare paired results and preserve failure cases |

Source tour: [pipeline](../src/scene_search/pipeline.py),
[search](../src/scene_search/search.py), [fusion](../src/scene_search/core.py),
[annotation protocol](../src/scene_search/annotations.py),
[evaluation](../src/scene_search/evaluate.py),
[protocol tests](../tests/test_annotation_protocol.py).

## Evidence and limits

The [October 27 report](LOCAL_RELEASE_RESULTS_2026-10-27.md) documents the owner's
three-video collection and exploratory weak-label measurements. Its 18-query
provisional test is already inspected and **not independent accuracy evidence**.
The new human-review tooling has automated tests; fresh human-reviewed labels
and real-model results have not been supplied with this change.

Core tests verify software contracts, not CLIP/ASR quality or browser playback.
The [fresh evaluation guide](HUMAN_EVALUATION.md) describes the remaining human
work. Model revisions are not fully pinned; preserve existing caches/manifests
and report their versions rather than promising byte-identical future downloads.

## Interview demonstration

Prepare an original or permission-cleared 60–90 second recording:

1. State the user problem and show the local corpus.
2. Run a visual query, a speech query and a mixed query.
3. Open returned timestamps and show the supporting evidence.
4. Show a failure and explain why the result needs human inspection.
5. End with the evaluation protocol, its current limitations and one next step.

No public hosting is required to present a local prototype honestly. Do not
include third-party media or private transcripts in a public demo without rights.

## Japanese project summary

映像フレームと音声の文字起こしを用いて、自然言語から該当シーンを検索する
ローカル実行型のプロトタイプです。CLIP・Whisper・テキスト埋め込み・FAISSを
組み合わせ、タイムスタンプ付きの検索結果を表示します。単一モダリティと
融合検索を比較する評価基盤、クエリと評価分割の固定、アノテーションの
レビュー記録を実装しています。既存の数値はAI支援ラベルによる探索的評価で、
独立した人手評価による精度は未検証です。

Use this description only where you can explain your own contribution. In an
application, separately identify personal design/debugging/testing work,
third-party models/libraries and any AI-assisted implementation.
