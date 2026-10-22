"""Run from the project root: python -m streamlit run app.py"""
import json
import os
from pathlib import Path

import streamlit as st

from scene_search.core import read_json, sha256, validate_labels
from scene_search.search import SearchEngine

st.set_page_config(page_title="Video Scene Search", page_icon="▶", layout="wide")
st.title("Video Scene Search")
st.caption("Find a moment through its images, its words, or both.")
root = Path(os.environ.get("SCENE_INDEX", "artifacts/index")).resolve()
if not (root / "build.json").is_file():
    st.info("Add your videos and build the index first. Run the commands below from the project folder.")
    st.code('scene-search ingest --manifest examples/corpus.json --output artifacts/index\n'
            'scene-search init-labels --index artifacts/index')
    st.caption("See README.md for video permissions, setup, and evaluation instructions.")
    st.stop()


@st.cache_resource
def load_engine(path, build_digest):
    return SearchEngine(path)


try:
    engine = load_engine(str(root), sha256(root / "build.json"))
except (ValueError, OSError, RuntimeError) as exc:
    st.error(f"Cannot load index: {exc}")
    st.stop()


def play(window):
    video = engine.videos[window["video_id"]]
    path = Path(video["path"])
    if path.is_file():
        st.video(str(path), start_time=int(window["start"]))
    else:
        st.warning("Source video was moved. Restore its original path or rebuild the index.")
    st.caption(f"{video['title']} · {window['start']:.1f}–{window['end']:.1f}s · {window['id']}")


with st.sidebar:
    st.header("Corpus")
    st.metric("Videos", len(engine.videos))
    st.metric("Search windows", len(engine.windows))
    st.caption(f"Frames every {engine.meta['frame_seconds']:g}s · Windows {engine.meta['window_seconds']:g}s")
    st.info("Use English for visual/hybrid queries. Transcript queries are multilingual; quality needs evaluation.")
    if not engine.segments:
        st.warning("No speech detected. Transcript search returns no results; hybrid uses visual ranking.")
    for v in engine.videos.values():
        with st.expander(v["title"]):
            st.write({k: v[k] for k in ("source", "license", "attribution")})

search_tab, annotation_tab = st.tabs(["Search", "Annotate before evaluating"])
with search_tab:
    with st.form("search_form"):
        query = st.text_input("Describe a moment", placeholder="Two people talking at a table", max_chars=500)
        mode = st.radio("Search method", ["visual", "transcript", "hybrid"], horizontal=True)
        submitted = st.form_submit_button("Search", type="primary")
    if submitted:
        try:
            with st.spinner("Searching… First search may download model weights."):
                st.session_state["results"] = engine.search(query, mode)
            st.session_state["last_query"] = query
        except (ValueError, OSError, RuntimeError) as exc:
            st.error(str(exc))
            st.session_state["results"] = []
    results = st.session_state.get("results", [])
    if submitted and not results:
        st.info("No indexed candidates for this search method.")
    if results:
        st.subheader(f"Results for: {st.session_state['last_query']}")
        chosen = st.selectbox("Play result", range(len(results)), format_func=lambda i:
            f"{i+1}. {results[i]['title']} · {results[i]['start']:.0f}s · {results[i]['mode']}")
        player, evidence = st.columns([3, 2])
        with player:
            play(results[chosen])
        with evidence:
            r = results[chosen]
            st.subheader("Evidence")
            if r["thumbnail"]:
                st.image(r["thumbnail"], caption="Representative frame from this window")
            st.write(r["transcript"] or "No transcript overlaps this window.")
            st.caption(f"Ranking score: {r['score']:.4f}. This is not a probability or confidence estimate.")
        st.dataframe([{k: r[k] for k in ("id", "title", "start", "end", "score")} for r in results],
                     hide_index=True)

with annotation_tab:
    st.subheader("Watch the source; label without using search results")
    st.write("Write queries before reviewing rankings. Mark every relevant 10-second window. "
             "Use the dev split to make choices; keep test labels fixed.")
    video_id = st.selectbox("Source video", list(engine.videos),
                            format_func=lambda vid: engine.videos[vid]["title"])
    video_windows = [w for w in engine.windows if w["video_id"] == video_id]
    window_id = st.selectbox("Browse a window", [w["id"] for w in video_windows],
                             format_func=lambda wid: f"{wid} · {engine.by_id[wid]['start']:.0f}s")
    play(engine.by_id[window_id])
    uploaded = st.file_uploader("Load labels.json (draft or previous annotations)", type=["json"])
    digest = sha256(root / "build.json")
    if uploaded is not None:
        try:
            payload = json.loads(uploaded.getvalue())
            if payload.get("build_sha256") != digest:
                st.error("This labels file belongs to a different build.")
            elif st.session_state.get("uploaded_labels") != uploaded.getvalue():
                st.session_state["annotations"] = payload
                st.session_state["uploaded_labels"] = uploaded.getvalue()
        except (ValueError, AttributeError):
            st.error("Invalid labels JSON.")
    if "annotations" not in st.session_state:
        st.session_state["annotations"] = {"status": "draft", "build_sha256": digest, "queries": []}
    labels = st.session_state["annotations"]
    if not isinstance(labels.get("queries"), list) or not all(isinstance(q, dict) for q in labels["queries"]):
        st.error("queries must be a list of objects. Reload a valid labels file.")
        st.stop()
    existing = {q.get("id", ""): q for q in labels["queries"]}
    selected = st.selectbox("Add or edit query", ["New query"] + list(existing))
    current = existing.get(selected, {})
    # Key the form by selected query so defaults refresh when switching entries.
    with st.form(f"annotation_{selected}"):
        qid = st.text_input("Query ID", value=current.get("id", f"q{len(existing)+1:02d}"))
        qtext = st.text_input("Query", value=current.get("text", ""), max_chars=500)
        kinds, splits = ["visual", "speech", "mixed"], ["dev", "test"]
        kind = st.selectbox("Query type", kinds, index=kinds.index(current.get("kind", "visual")))
        split = st.selectbox("Split", splits, index=splits.index(current.get("split", "test")))
        relevant = st.multiselect("All relevant window IDs", list(engine.by_id),
                                  default=[w for w in current.get("relevant", []) if w in engine.by_id])
        if st.form_submit_button("Save query in this session"):
            if not qid.strip() or not qtext.strip() or not relevant:
                st.error("Provide an ID, query and at least one relevant window.")
            elif qid != selected and qid in existing:
                st.error("That ID already exists. Select it to edit.")
            else:
                labels["queries"] = [q for q in labels["queries"] if q.get("id") != selected]
                labels["queries"].append({"id": qid.strip(), "text": qtext.strip(), "kind": kind,
                                          "split": split, "relevant": relevant})
                st.success("Saved in this session. Download labels below to keep your work.")
    st.caption(f"{len(labels['queries'])} queries. Target: 24 total, including 6 dev and 18 test.")
    reviewed = st.checkbox("I reviewed every query and all relevant windows; mark annotations complete")
    export = {**labels, "status": "annotated" if reviewed else "draft"}
    valid = True
    if reviewed:
        try:
            validate_labels(export, engine.windows)
        except ValueError as exc:
            st.error(str(exc))
            valid = False
    st.download_button("Download labels.json", json.dumps(export, ensure_ascii=False, indent=2),
                       file_name="labels.json", mime="application/json", disabled=not valid)
    st.caption("Annotations live only in this browser session until downloaded. "
               "Place the downloaded file in evaluation/labels.json before running evaluation.")
