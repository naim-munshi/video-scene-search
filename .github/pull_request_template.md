## Summary

What changed and why?

## Verification

- [ ] `python -m compileall -q src app.py scripts tests`
- [ ] `PYTHONPATH=src python -m unittest discover -s tests -v`
- [ ] `python scripts/check_repository_hygiene.py`
- [ ] Relevant Mac/native checks described if applicable
- [ ] Documentation updated when behavior changes

## Security and evidence

- [ ] No videos, transcripts, private annotations, FAISS files, caches, credentials or reports committed
- [ ] No unsupported claims of model accuracy, Safari playback or secure public hosting
- [ ] New performance claims identify split, query count, ground-truth provenance and raw comparison evidence

## Compatibility

Does this change require re-ingestion, retraining, new model downloads or migration? If yes, document the new index/output directory; **do not overwrite** historical evidence.
