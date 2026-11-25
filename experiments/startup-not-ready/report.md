# ForgeAI quality report

Run status: **failed**

Model: `qwen2.5-3b`. Real local inference; 1 calls, 2248 reported/reserved tokens.

## Development evaluations

| Version | Passed | Rate | Selected |
|---|---:|---:|---|

## Holdout (never used to choose patches)

Not completed. No holdout quality claim is made.

## Remaining observed failures

No failures observed in the completed cases; this does not establish perfect correctness.

## Incomplete work

Local model request failed at intake-brief: HTTP Error 503: Service Unavailable

## Changes and tradeoffs

No repair was applied.

## Limits of this evidence

- The same small model generates tests and supplies semantic judgments: correlated mistakes and self-preference remain possible. The judge sees no model identity or competing answer and receives no reward for verbosity; deterministic quote checks cannot establish semantic entailment.
- Expected facts are verified verbatim against sources; the questions, refusal labels and coverage claims still require human review. A wrong test oracle can distort scores.
- BM25 can miss paraphrases. PDFs need extractable text; scanned pages have no automatic OCR. Tables in PDFs may lose layout.
- The optimizer sees development failures only. Holdout remains a small in-domain check, not an unseen-domain benchmark.
- Corpus text and model call transcripts are stored locally in artifacts. Do not publish runs containing confidential input.
- Source prompt injection, model errors and incorrect tool arguments remain risks. Tools are read-only and bounded; no generated code is executed.
- Live date values depend on the run date. No external weather or paid service is required.
