# Mac-এ চালানোর নিয়ম

## ২৭ অক্টোবর: প্রজেক্টের local engineering release বন্ধ (CLOSED)

তোমার Mac-এ **৩টি ভিডিও, ২৪টি query, dev/test benchmark** সফলভাবে চালানো হয়েছে।
নতুন করে ভিডিও download বা evaluation চালানোর প্রয়োজন নেই। এখন শুধু
video+audio decode যাচাই এবং চাইলে Safari playback-এর ৯টি manual check:

```bash
cd ~/video-scene-search
source .venv/bin/activate
git pull --ff-only origin MdNaim
python scripts/media_playback_preflight.py --index artifacts/portfolio-real-v2
SCENE_INDEX=artifacts/portfolio-real-v2 python -m streamlit run app.py --server.address 127.0.0.1
```

Browser-এ **Video library** থেকে NASA / Interview / Tears of Steel-এ
একটি একটি করে Beginning, Middle, Near end নির্বাচন করে play করো।
ছবি ও শব্দ ঠিক থাকলে checkbox tick দাও। ৯টি হলে নিজের manual
playback report download করতে পারবে। এটি automated Safari test নয়।
AI-assisted query labels এখনো independently verified নয়।

সম্পূর্ণ status: `docs/PROJECT_CLOSURE.md`।

---


## বর্তমানে তৈরি তিন-ভিডিও প্রজেক্টের Final Engineering Check (এই অংশটাই এখন ব্যবহার করো)

তোমার Mac-এ NASA, Interview ও Tears of Steel আগেই indexed হয়েছে।
**নতুন করে ভিডিও download, ingest বা query লেখার প্রয়োজন নেই।**

Terminal-এ একবার পুরো block copy-paste করো:

```bash
cd ~/video-scene-search
source .venv/bin/activate
git pull --ff-only origin MdNaim

python scripts/finish_portfolio.py --preflight-only
python scripts/finish_portfolio.py --device mps

LATEST=$(ls -dt reports/portfolio-release-* | head -n 1)
cat "$LATEST/RELEASE_SUMMARY.md"
open -R "$LATEST/shareable-release-evidence.zip"
```

এই script আগের v2 index, ২৪টি query-এর JSON এবং Mac-এ cached models দিয়ে
৬টি dev ও ১৮টি test query-এর **preliminary AI-assisted report** তৈরি করবে।
সব result থাকবে নতুন reports/portfolio-release-... folder-এ।
আগের video, labels, index, report বা Mac-এর OS বদলাবে না।

কোনো error হলে শেষের Terminal output পাঠাও। Successful হলে
shareable-release-evidence.zip file-টি upload করো, ফলাফল review করা যাবে।

**মনে রাখবে:** AI-assisted labels দিয়ে পাওয়া score human-verified real-world
accuracy নয়। Full Safari playback acceptance, independent ground-truth review
এবং demo recording আলাদা sign-off। বিস্তারিত docs/PORTFOLIO_COMPLETION.md।

---

## ১. Python environment

ZIP extract করে `video-scene-search` folder-এ Terminal খুলবে। Python 3.12 লাগবে।
তোমার default Python 3.14 হলে সেটা বদলাবে না; 3.12 দিয়ে আলাদা environment বানাবে।

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover -s tests -v
```

`python3.12: command not found` হলে Homebrew ব্যবহার করলে:

```bash
brew install python@3.12
```

## ২. একটি নিজের ভিডিও যোগ করো

```bash
mkdir -p data/videos
```

এই folder-এ তোমার ভিডিও `video_01.mp4` নামে রাখবে।
`examples/corpus.json` খুলে title/source/attribution ঠিক করবে। ভিডিও ব্যবহারের
অনুমতি নিশ্চিত হলে `rights_confirmed`-এর `false` বদলে `true` করবে।
আরও ভিডিও যোগ করতে একই `videos` list-এ আলাদা ID-সহ object যোগ করবে।

## ৩. Index ও UI

```bash
scene-search ingest --manifest examples/corpus.json --output artifacts/index
scene-search init-labels --index artifacts/index --output evaluation/labels.json
python -m streamlit run app.py
```

Browser-এ `http://127.0.0.1:8501` খুলবে। প্রথমবার model download হবে।
Visual/hybrid search-এ শুরুতে English query ব্যবহার করবে।
যেমন: `Two people talking at a table`। Result বেছে নিলে সেই সময় থেকে ভিডিও চলবে।

## ৪. মূল্যায়ন

UI-এর annotation tab-এ `evaluation/labels.json` load করবে।
ভিডিও নিজে দেখে query লিখবে ও সঠিক window ID বেছে নেবে। মোট ২৪টি query রাখবে:
৬টি dev, ১৮টি test। Search results দেখে ground truth বানাবে না।

Query save করলে সেটা শুধু session-এ থাকে। কাজের শেষে `Download labels.json`
চাপবে। Download করা file-টি project-এর `evaluation/labels.json` হিসেবে রাখবে।
সব query যাচাই শেষ হলে reviewed checkbox দিয়ে annotated file download করবে।

```bash
scene-search evaluate --labels evaluation/labels.json --split dev --output reports/dev-v1
scene-search evaluate --labels evaluation/labels.json --split test --output reports/test-v1
```

`reports/test-v1/report.md`-তে তুলনার table ও ভুল ফলের তালিকা পাবে।
কেন ভুল হয়েছে তা ভিডিও দেখে লিখবে। তারপর বাস্তব সংখ্যাগুলো README/CV-তে যোগ করবে।

একই output folder দ্বিতীয়বার overwrite হবে না। নতুন run হলে `test-v2` ব্যবহার করবে।
এই project-এর সঙ্গে বাস্তব ভিডিও বা বানানো accuracy সংখ্যা দেওয়া হয়নি।

## ৫. Mac-এর verified demo index ও fusion update

আগে তৈরি `artifacts/demo-index-isolated` মুছে ফেলবে না।
নতুন কোড এবং integrity check চালাও:

```bash
git pull --ff-only origin MdNaim
python -m pip install -e .
python scripts/acceptance_check.py --index artifacts/demo-index-isolated
scene-search search "project deadline" --index artifacts/demo-index-isolated --mode hybrid --device mps
scene-search evaluate --index artifacts/demo-index-isolated --labels evaluation/demo-labels-isolated.json --split dev --output reports/demo-dev-intent-v1 --device mps
cat reports/demo-dev-intent-v1/report.md
```

এরপর বাস্তব ভিডিও ও মানুষ যাচাই করা label ছাড়া retrieval accuracy দাবি করবে না।

## ৬. Free-source ভিডিও সংগ্রহ

৩টি অনুমতিসহ ভিডিওর download script যোগ হয়েছে। Mac-এ:

```bash
cd ~/video-scene-search
source .venv/bin/activate
git pull --ff-only origin MdNaim
python scripts/prepare_portfolio_videos.py --plan
python scripts/prepare_portfolio_videos.py
python scripts/real_video_preflight.py --manifest data/portfolio-corpus.json
```

ভিডিওগুলো থাকবে `data/videos/`-এ, manifest `data/portfolio-corpus.json`।
Source size বড়; শুধু ২টি চাইলে `--only interview nasa` দাও।
Details: `docs/VIDEO_SOURCES.md`। Attribution বাধ্যতামূলক।


## ৭. Professional web UI ও real video select করা

Browser-এ যদি Synthetic demo 1, 2, 3 দেখায় এবং ৯টি windows থাকে, তা
হলে ভুল index খোলা আছে। ৩টি বাস্তব ভিডিওর build সম্পূর্ণ হলে:

```bash
cd ~/video-scene-search
source .venv/bin/activate
git pull --ff-only origin MdNaim
SCENE_INDEX=artifacts/portfolio-real-v2 python -m streamlit run app.py
```

Sidebar-এর **Active video collection** থেকে portfolio-real-v2 বেছে নাও।
যদি v2 না পাওয়া যায়, docs/ADD_THIRD_VIDEO.md অনুসারে NASA video append
করো। v1-এ শুধু interview ও Tears of Steel আছে।

নতুন UI-তে আছে Search, Evaluate & annotate, Video library এবং Add videos।
Add videos tab কেবল নতুন licensed MP4 (250 MiB-এর কম) local-এ stage করে।
এটি স্বয়ংক্রিয়ভাবে index তৈরি করে না। Tab-এর Terminal command চালিয়ে
নতুন index তৈরি করতে হবে। তোমার NASA / interview / film আবার upload নয়।
