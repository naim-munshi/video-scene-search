"""Ranking-free local annotation workbench. Run on loopback only."""
import os
import shlex
import sys
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from scene_search.core import read_json
from scene_search.review import (load_corpus, new_session, latest_labels, save_queries,
                                 freeze_session, save_review, finalize_session)

st.set_page_config(page_title="Video Scene Search · Human review", page_icon="🎬", layout="wide")
st.title("Review the footage. Build the evidence.")
st.caption("Local annotation workbench · no search rankings · no model inference")
index = Path(os.environ.get("SCENE_INDEX", str(ROOT / "artifacts/portfolio-real-v2"))).expanduser().resolve()
workspace = Path(os.environ.get("SCENE_REVIEW_DIR", str(ROOT / "evaluation/human-review"))).expanduser().resolve()
try:
    corpus = load_corpus(index)
except (OSError, ValueError, KeyError, TypeError) as exc:
    st.error(f"Cannot open your local collection: {exc}")
    st.info("Run on the Mac containing your existing index. Set SCENE_INDEX to that index folder.")
    st.stop()

with st.sidebar:
    st.header("Your review sessions")
    with st.expander("Create a fresh study"):
        count = st.number_input("Total queries", min_value=2, max_value=128, value=48)
        dev = st.number_input("Development queries", min_value=1, max_value=int(count)-1,
                              value=min(12, int(count)-1))
        if st.button("Create review session"):
            name = datetime.now().strftime("study-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
            new_session(index, workspace / name, int(count), int(dev))
            st.session_state["session_choice"] = name
    sessions = sorted([p.name for p in workspace.glob("study-*") if (p / "draft.json").is_file()], reverse=True)
    if not sessions:
        st.info("Create a study to begin. Your videos and existing labels stay unchanged.")
        st.stop()
    selected = st.selectbox("Resume saved session", sessions, key="session_choice")
    session = workspace / selected
    st.caption("Each save creates a new local checkpoint. Refreshing the browser does not erase saved work.")
    st.code(str(session), language=None)

labels_path = latest_labels(session)
labels = read_json(labels_path)
if labels.get("build_sha256") != corpus["build_sha256"]:
    st.error("This session belongs to a different index. Select its original collection or create a new study.")
    st.stop()
frozen = (session / "plan.json").exists()
finalized = (session / "reviewed.json").exists()
reviewed_count = sum(q.get("review", {}).get("reviewed") is True for q in labels["queries"])
cols = st.columns(3)
cols[0].metric("Source videos", len(corpus["videos"]))
cols[1].metric("Queries reviewed", f"{reviewed_count}/{len(labels['queries'])}")
cols[2].metric("Study phase", "Finalized" if finalized else "Review" if frozen else "Write queries")

if not frozen:
    st.subheader("1. Write fresh questions")
    st.write("Watch the original footage, then write answerable questions. Do not copy the old 24-query set "
             "or consult search results. Save your work, then freeze the questions and splits.")
    rows = [{k: q[k] for k in ("id", "text", "kind", "split")} for q in labels["queries"]]
    edited = st.data_editor(rows, disabled=["id"], hide_index=True, width="stretch",
                            column_config={
                                "text": st.column_config.TextColumn("Question", width="large", max_chars=500),
                                "kind": st.column_config.SelectboxColumn("Evidence type", options=["visual", "speech", "mixed"]),
                                "split": st.column_config.SelectboxColumn("Split", options=["dev", "test"])},
                            key=f"queries-{selected}")
    if st.button("Save questions"):
        try:
            save_queries(session, edited)
            st.success("Questions saved locally. Blank questions can be completed later.")
        except (OSError, ValueError) as exc:
            st.error(str(exc))
    if st.button("Save and freeze questions", type="primary"):
        try:
            save_queries(session, edited)
            freeze_session(index, session)
            st.rerun()
        except (OSError, ValueError) as exc:
            st.error(str(exc))

st.subheader("Watch original source footage")
videos = {v["id"]: v for v in corpus["videos"]}
vid = st.selectbox("Source video", list(videos), format_func=lambda key: videos[key].get("title", key))
windows = [w for w in corpus["windows"] if w["video_id"] == vid]
by_id = {w["id"]: w for w in corpus["windows"]}
wid = st.selectbox("Jump to a window", [w["id"] for w in windows],
                    format_func=lambda key: f"{key} · {by_id[key]['start']:.0f}–{by_id[key]['end']:.0f}s")
source = Path(videos[vid]["path"])
if source.is_file():
    st.video(str(source), start_time=int(by_id[wid]["start"]))
else:
    st.warning("Source media is missing on this machine. Restore its original path before reviewing it.")
st.caption("Use all source videos where relevant. Sparse thumbnails or ASR alone can miss evidence.")

if frozen and not finalized:
    st.subheader("2. Label each frozen question")
    qid = st.selectbox("Question to review", [q["id"] for q in labels["queries"]],
                       key=f"question-{selected}")
    current = next(q for q in labels["queries"] if q["id"] == qid)
    st.write(current["text"])
    st.caption(f"{current['kind']} · {current['split']} · frozen question")
    with st.form(f"review-{selected}-{qid}"):
        relevant = st.multiselect("All relevant windows across the collection", list(by_id),
                                   default=current.get("relevant", []))
        review = current.get("review", {})
        reviewer = st.text_input("Reviewer alias", value=review.get("reviewer", ""))
        note = st.text_area("Evidence and timestamps", value=review.get("evidence_note", ""),
                             help="Explain what you saw or heard and why these windows answer the question.")
        confirmed = st.checkbox("I watched the original source and checked every relevant window",
                                value=False)
        if st.form_submit_button("Save reviewed question", type="primary"):
            try:
                if not all(Path(v["path"]).is_file() for v in corpus["videos"]):
                    raise ValueError("Restore all original videos before recording a completed review")
                save_review(index, session, qid, relevant, reviewer, note, confirmed)
                st.rerun()
            except (OSError, ValueError) as exc:
                st.error(str(exc))
    st.info("No genuine match? Do not invent one. Record the ambiguity and revise the study before evaluation.")
    if st.button("Finalize human-review labels", disabled=reviewed_count != len(labels["queries"])):
        try:
            finalize_session(index, session)
            st.rerun()
        except (OSError, ValueError) as exc:
            st.error(str(exc))

if finalized:
    st.success("Review records validated and saved. Human review is self-reported, not independently certified.")
    st.subheader("3. Run the real-model evaluation on this Mac")
    for split in ("dev", "test"):
        cmd = [sys.executable, "-m", "scene_search.cli", "evaluate", "--index", str(index),
               "--labels", str(session / "reviewed.json"), "--plan", str(session / "plan.json"),
               "--split", split, "--compare-equal-rrf", "--offline",
               "--output", str(ROOT / "reports" / f"{selected}-{split}")]
        st.caption("Run development first; choose settings without inspecting test results." if split == "dev"
                   else "Only run test after fixing code and settings. Do not tune on test outcomes.")
        st.code("PYTHONPATH=src " + shlex.join(cmd), language="bash")

st.caption("Private local study files remain under evaluation/. They are excluded from Git. "
           "This workbench never sends media to a model provider or computes search rankings.")
