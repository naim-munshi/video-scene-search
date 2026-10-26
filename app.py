"""Local-only Streamlit console for timestamped multimodal video retrieval."""
import json
import os
import shlex
import subprocess
from html import escape
from pathlib import Path

import streamlit as st

from scene_search.core import sha256, validate_labels
from scene_search.search import SearchEngine
from scene_search.ui_helpers import (
    discover_indexes, format_index, is_synthetic, readable_time,
)

APP_ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Video Scene Search | Media Intelligence",
                   page_icon="🎞️", layout="wide",
                   initial_sidebar_state="expanded")
stylesheet = APP_ROOT / ".streamlit" / "style.css"
if stylesheet.is_file():
    st.markdown("<style>" + stylesheet.read_text(encoding="utf-8") + "</style>",
                unsafe_allow_html=True)

configured = Path(os.environ.get(
    "SCENE_INDEX", str(APP_ROOT / "artifacts" / "index"))).expanduser().resolve()
available = discover_indexes(APP_ROOT / "artifacts", configured)

with st.sidebar:
    st.markdown(
        '<div class="vss-brand">◉ &nbsp; VIDEO <span class="vss-dot">SCENE</span> SEARCH</div>'
        '<div class="vss-sidebar-sub">Local multimodal media intelligence</div>',
        unsafe_allow_html=True)
    if not available:
        st.warning("No completed index found. Build a local video index first.")
        st.code("scene-search ingest --manifest data/portfolio-corpus.json "
                "--output artifacts/portfolio-real-v1 --device mps")
        st.stop()
    root = st.selectbox("Active video collection", available,
                        format_func=format_index, key="active_index")
    if st.session_state.get("_loaded_index") != str(root):
        for key in ("results", "last_query", "annotations", "uploaded_labels"):
            st.session_state.pop(key, None)
        st.session_state["_loaded_index"] = str(root)


@st.cache_resource(show_spinner="Opening video index…")
def load_engine(path, build_digest):
    return SearchEngine(path)


try:
    engine = load_engine(str(root), sha256(root / "build.json"))
except (OSError, RuntimeError, ValueError, KeyError) as exc:
    st.error(f"Cannot load this index: {exc}")
    st.stop()

synthetic = is_synthetic(engine.videos)
video_rows = list(engine.videos.values())
duration = sum(float(v.get("duration", 0)) for v in video_rows)


def play(window):
    video = engine.videos[window["video_id"]]
    path = Path(video["path"])
    if path.is_file():
        st.video(str(path), start_time=int(window["start"]))
    else:
        st.warning("Source video was moved. Restore its original path or rebuild.")
    st.caption(
        f"{video['title']} · {readable_time(window['start'])}"
        f"–{readable_time(window['end'])} · {window['id']}"
    )


with st.sidebar:
    st.divider()
    st.caption("VIDEO LIBRARY")
    for video in video_rows:
        st.markdown(
            '<div class="vss-video-title" style="color:#F3FAF8">'
            + escape(str(video.get("title", "Untitled"))) + '</div>'
            + '<div class="vss-sidebar-sub">'
            + readable_time(video.get("duration", 0)) + ' · '
            + escape(str(video.get("id", ""))) + '</div>',
            unsafe_allow_html=True)
    if synthetic:
        st.warning("Demo is selected. Switch to portfolio-real-v1/v2 for real videos.")
    else:
        st.success("Local video collection ready")
    if not engine.segments:
        st.warning("Speech is absent; transcript search has no candidates.")
    st.divider()
    st.caption("PRIVATE BY DEFAULT")
    st.caption("Your local videos and FAISS indexes are not uploaded to GitHub.")
    st.caption(f"Collection: {root.name}")


st.markdown(
    '<div class="vss-hero">'
    '<div class="vss-eyebrow">MEDIA INTELLIGENCE / MULTIMODAL SEARCH</div>'
    '<h1>Find the exact moment.</h1>'
    '<p>Search across visual scenes and spoken words. Jump directly '
    'to the timestamp and inspect the evidence behind each match.</p>'
    '<div class="vss-hero-tags">'
    '<span class="vss-tag">Visual retrieval</span>'
    '<span class="vss-tag">Speech retrieval</span>'
    '<span class="vss-tag">Hybrid ranking</span>'
    '<span class="vss-tag">Local · Private</span>'
    '</div></div>', unsafe_allow_html=True)

stats = st.columns(4)
for column, label, value in zip(
    stats,
    ("Videos", "Search windows", "Speech segments", "Footage"),
    (str(len(video_rows)), str(len(engine.windows)),
     str(len(engine.segments)), readable_time(duration)),
):
    with column:
        st.markdown(
            '<div class="vss-stat"><div class="vss-stat-label">' + label
            + '</div><div class="vss-stat-value">' + value
            + '</div></div>', unsafe_allow_html=True)

if synthetic:
    st.info("This is the synthetic demo. Use the left collection selector "
            "to open portfolio-real-v1 (2 real videos), or portfolio-real-v2 "
            "(3 real videos, once extension succeeds).")

search_tab, annotation_tab, library_tab, import_tab = st.tabs(
    ["🔎 Search", "📝 Evaluate & annotate", "🎞 Video library", "＋ Add videos"]
)
with search_tab:
    st.markdown('<div class="vss-section-heading">Search your collection</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="vss-section-help">Describe a topic, dialogue, scene '
        'or object. Every match has a source timestamp.</div>',
        unsafe_allow_html=True)
    with st.form("search_form"):
        query = st.text_input(
            "Describe a moment",
            placeholder="An astronaut discussing a lunar mission",
            max_chars=500)
        mode = st.radio(
            "Search method", ["hybrid", "visual", "transcript"],
            format_func=lambda m: {
                "hybrid": "Hybrid · recommended",
                "visual": "Visual · what is shown",
                "transcript": "Transcript · what was said",
            }[m], horizontal=True)
        st.caption("Visual search works best with English descriptions. "
                   "Transcript embeddings are multilingual.")
        submitted = st.form_submit_button("Search scenes", type="primary")
    if submitted:
        try:
            with st.spinner("Searching images and speech transcripts…"):
                st.session_state["results"] = engine.search(query, mode)
            st.session_state["last_query"] = query.strip()
        except (ValueError, OSError, RuntimeError, KeyError) as exc:
            st.error(f"Search failed: {exc}")
            st.session_state["results"] = []
    results = st.session_state.get("results", [])
    if submitted and not results:
        st.info("No matching windows were found.")
    if results:
        st.subheader(f"Matches for: {st.session_state.get('last_query', '')}")
        st.caption(f"{len(results)} ranked results · scores are not probabilities")
        chosen = st.selectbox(
            "Play a matching moment", range(len(results)),
            format_func=lambda i: (
                f"{i+1:02d} · {results[i]['title']} "
                f"· {readable_time(results[i]['start'])}"
            ))
        player, details = st.columns([1.65, 1], gap="large")
        with player:
            play(results[chosen])
        with details:
            result = results[chosen]
            st.markdown("#### Evidence")
            thumb = result.get("thumbnail")
            if thumb and Path(thumb).is_file():
                st.image(thumb, caption="Representative frame",
                         use_container_width=True)
            st.markdown("**Speech near this moment**")
            st.write(result.get("transcript") or
                     "No transcript overlaps this window.")
            st.caption(f"Ranking score: {result['score']:.4f} "
                       "(not a calibrated confidence)")
        st.markdown("#### All matches")
        st.dataframe(
            [{"Rank": i + 1, "Video": r["title"],
              "Start": readable_time(r["start"]),
              "End": readable_time(r["end"]),
              "Score": round(r["score"], 5),
              "Window ID": r["id"]}
             for i, r in enumerate(results)],
            hide_index=True, use_container_width=True)
    else:
        st.caption("Try: 'People talking in an interview', "
                   "'Two people standing outdoors', or 'NASA lunar rover'.")

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


with library_tab:
    st.markdown('<div class="vss-section-heading">Indexed video library</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="vss-section-help">Preview footage, verify video origins, '
        'and browse timestamp windows.</div>', unsafe_allow_html=True)
    library_id = st.selectbox(
        "Choose a source video", list(engine.videos),
        format_func=lambda vid: engine.videos[vid]["title"],
        key="library_source_video")
    source = engine.videos[library_id]
    video_windows = [w for w in engine.windows if w["video_id"] == library_id]
    preview, info = st.columns([1.6, 1], gap="large")
    with preview:
        media_path = Path(source["path"])
        if media_path.is_file():
            st.video(str(media_path))
        else:
            st.warning("Original video is missing from its saved path.")
    with info:
        st.markdown("#### Source details")
        st.markdown(f"**{source.get('title', 'Untitled')}**")
        st.caption(
            f"{readable_time(source.get('duration', 0))} duration "
            f"· {len(video_windows)} indexed windows")
        st.markdown("**Origin**")
        st.write(source.get("source") or "Not recorded")
        st.markdown("**License**")
        st.write(source.get("license") or "Not recorded")
        st.markdown("**Attribution**")
        st.write(source.get("attribution") or "Not recorded")
    with st.expander("Browse indexed timestamps"):
        st.dataframe(
            [{"Window": w["id"], "From": readable_time(w["start"]),
              "To": readable_time(w["end"])} for w in video_windows],
            hide_index=True, use_container_width=True)

with import_tab:
    st.markdown('<div class="vss-section-heading">Add a video from this Mac</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="vss-section-help">New videos are staged in a separate '
        'local corpus. Existing search indexes and annotations are not overwritten.</div>',
        unsafe_allow_html=True)
    st.info("Already downloaded Interview, Tears of Steel and NASA? "
            "Do not upload them again. Select portfolio-real-v2 in the sidebar "
            "after the NASA extension completes (instructions: docs/ADD_THIRD_VIDEO.md).")
    uploaded_video = st.file_uploader(
        "Choose one MP4 file · 250 MiB limit",
        type=["mp4"], key="local_video_upload")
    with st.form("import_video_form"):
        new_title = st.text_input("Title", placeholder="My own interview")
        new_source = st.text_input(
            "Origin / recording date", placeholder="Recorded by me in October 2026")
        new_license = st.text_input(
            "License / consent", placeholder="Self-owned, all participants consented")
        new_attribution = st.text_input(
            "Author credit", placeholder="Creator or camera operator")
        rights = st.checkbox(
            "I have the rights and participant consent to process this video")
        import_submit = st.form_submit_button("Stage video locally", type="primary")
    if import_submit:
        if uploaded_video is None:
            st.error("Select an MP4 file first.")
        else:
            try:
                from scene_search.uploads import stage_upload
                with st.spinner("Checking media and saving a new local corpus…"):
                    item = stage_upload(
                        uploaded_video, new_title, new_source,
                        new_license, new_attribution, rights,
                        APP_ROOT / "data" / "imports")
                st.success("Saved as a separate local corpus. No index was modified.")
                command = (
                    "scene-search ingest "
                    f"--manifest {shlex.quote(item['manifest'])} "
                    f"--output {shlex.quote(item['output'])} "
                    "--device mps --language en")
                st.code(command, language="bash")
                st.caption("Run the command in Mac Terminal, then refresh this "
                           "page and select the newly created index.")
            except (ValueError, OSError, RuntimeError,
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired) as exc:
                st.error(f"Video staging failed: {exc}")
    st.caption("Local import is limited to 250 MiB and requires MP4 audio "
               "and video streams. Public hosting is not supported.")
