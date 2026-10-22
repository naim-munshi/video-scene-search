# Mac-এ চালানোর নিয়ম

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
