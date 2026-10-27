# Real-video evaluation: 24 candidate queries (Bengali guide)

**Warning:** All candidate texts below are hypotheses based on video genres and
a few screenshots; they are NOT annotated ground truth, and not all may exist
in the videos. Watch the footage and edit/remove/rewrite any query that has
no verified relevant scene or spoken passage. NEVER fill relevant window IDs
from the AI's own search ranking, especially on the held-out test split.

## Seed the 24-query draft without overwriting the original

\`\`\`bash
cd ~/video-scene-search
source .venv/bin/activate
git pull --ff-only origin MdNaim

python scripts/seed_portfolio_queries.py
open -R evaluation/portfolio-real-v2-query-draft.json
\`\`\`

The script reads evaluation/portfolio-real-v2-labels.json and checks that
its build_sha256 matches artifacts/portfolio-real-v2/build.json. It fills
blank query text and type, retaining any human-written query or relevance
labels already in the original file. It writes a NEW JSON file. Neither the
original template nor the underlying index is modified.

## Query reference

| ID | Video | Text (suggested) | Type | Split |
|---|---|---|---|---|
| q01 | NASA | A person describes a lunar or space mission. | speech | dev |
| q02 | NASA | A man sits beside scientific equipment. | visual | dev |
| q03 | Interview | An older man in a dark shirt speaking in an interview. | visual | dev |
| q04 | Interview | An interviewee answers a question about technology. | speech | dev |
| q05 | Tears of Steel | A futuristic machine or structure is shown. | visual | dev |
| q06 | Tears of Steel | A character speaks during a science fiction scene. | mixed | dev |
| q07 | Interview | A close-up of the interviewee's face. | visual | test |
| q08 | Interview | The guest speaks about computers. | speech | test |
| q09 | Interview | The interviewee explains an idea while on camera. | mixed | test |
| q10 | Interview | An interview shot shows the speaker seated. | visual | test |
| q11 | Interview | Someone mentions engineering or electronics. | speech | test |
| q12 | Interview | The guest speaks while making a hand gesture. | mixed | test |
| q13 | Tears of Steel | Two people appear together in a live-action shot. | visual | test |
| q14 | Tears of Steel | A futuristic vehicle or mechanical object appears. | visual | test |
| q15 | Tears of Steel | One character speaks to another character. | speech | test |
| q16 | Tears of Steel | A conversation takes place inside a building. | mixed | test |
| q17 | Tears of Steel | A scene contains computer-generated visual effects. | visual | test |
| q18 | Tears of Steel | Someone talks while futuristic machinery is visible. | mixed | test |
| q19 | NASA | Aerospace machinery is visible in archival footage. | visual | test |
| q20 | NASA | A narrator talks about a space mission. | speech | test |
| q21 | NASA | A man speaks while scientific equipment is visible. | mixed | test |
| q22 | NASA | A close-up of a person appears in the NASA footage. | visual | test |
| q23 | NASA | A speaker discusses travel or a mission. | speech | test |
| q24 | NASA | Archival space-program footage accompanies spoken explanation. | mixed | test |

## How to hand-label safely

In Streamlit choose **Evaluate & annotate** and upload the new
portfolio-real-v2-query-draft.json. The source video picker is for playback,
not a ground-truth filter. Choose the corresponding video, watch or listen,
inspect which original 10-second windows genuinely satisfy the query and
select **every** relevant window ID. These appear in forms like:

- portfolio_interview:00000 (00:00–00:10)
- portfolio_film:00073 (12:10–12:14, if the video's final partial window)
- portfolio_nasa:00011 (01:50–02:00)

An ID's structure is video_id + ":" + five-digit zero-based window number,
with ten-second default windows. The example IDs are explanations of
format/timestamp only, not asserted relevance labels. Since the project
returns 10-second windows, a verified event crossing a boundary can make
two adjacent windows relevant.

If a proposed speech claim is **not audible**, or visual element is **not
present**, rewrite that candidate query to something genuinely observable.
If no such window exists, do not force an irrelevant label just to fill
24 rows. A ground-truth test set cannot be defined by the model's predictions.

For q01–q06, use dev labels for error analysis and tuning. Keep q07–q24
sealed, then evaluate the held-out test split once after freezing
your models and ranking policy.

## Save and evaluate

Select "I reviewed every query..." only once all 24 have been verified,
then download labels.json from Streamlit and place it at
evaluation/portfolio-real-v2-annotated.json.

\`\`\`bash
scene-search evaluate \
  --index artifacts/portfolio-real-v2 \
  --labels evaluation/portfolio-real-v2-annotated.json \
  --split dev \
  --output reports/portfolio-real-dev-v1 \
  --device mps
\`\`\`

When configuration is frozen, create a separate test report using
--split test and a **new** --output directory; do not overwrite evidence.
