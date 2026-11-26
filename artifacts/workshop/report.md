# ForgeAI quality report

Run status: **completed**

Model: `qwen3-4b-instruct-2507`. Real local inference; 171 calls, 161308 reported/reserved tokens.

## Development evaluations

| Version | Passed | Rate | Selected |
|---|---:|---:|---|
| 1 | 14/18 | 77.8% | no |
| 2 | 17/18 | 94.4% | yes |
| 3 | 16/18 | 88.9% | no |

## Holdout (never used to choose patches)

6/6 passed (100.0%). This small, model-generated sample is not an estimate of production accuracy.

## Remaining observed failures

Recovery reused 140 exact recorded model responses; 31 calls were newly executed. See recovery.json. Reuse is not new inference; resource totals include prior usage and a conservative interrupted-request reservation.

- E08 (development, hallucination): The question asks specifically for the access hours of the Riverside Tide Workshop on Saturday. The expected fact states clearly that it opens Saturday from 10:00 to 16:00, which directly answers the question. The candidate refuses to answer and cites inability to verify evidence, despite having a clear, directly cited source in the expected facts. This refusal contradicts the expected status of 'answered' and fails to provide the correct information even when it is explicitly available.

## Changes and tradeoffs

- reduce_wrong_refusal: The failures involving wrong refusals (E15 and E16) stem from the agent incorrectly refusing to answer questions where the evidence directly and explicitly supports a response. In E16, the policies clearly state prohibitions on including medical information and lending membership cards, making the answer directly derivable. In E15, while the refusal is justified due to an implied rule not present in the policy, the agent fails to recognize that the evidence supports a direct answer to the stated facts. The 'reduce_wrong_refusal' patch ensures that when evidence directly answers a question within scope, the agent answers with the exact facts, even if the question phrasing differs. This directly addresses the hallucination and wrong refusal failures by enforcing a stricter rule: if the evidence supports an answer, it must be provided, not refused without justification. Accepted: True; before 0.7778, after 0.9444.
- source_only: The failure is a hallucination caused by the agent refusing to answer a question that is directly supported by the expected facts. The agent incorrectly cites an inability to verify evidence, despite having a clear, explicitly stated source in the expected facts. Applying the 'source_only' patch ensures the agent only states information directly entailed by quoted evidence, preventing unsupported refusals and enforcing accurate, source-backed responses. Accepted: False; before 0.9444, after 0.8889.

## Limits of this evidence

- The same small model generates tests and supplies semantic judgments: correlated mistakes and self-preference remain possible. The judge sees no model identity or competing answer and receives no reward for verbosity; deterministic quote checks cannot establish semantic entailment.
- Expected facts are verified verbatim against sources; the questions, refusal labels and coverage claims still require human review. A wrong test oracle can distort scores.
- BM25 can miss paraphrases. PDFs need extractable text; scanned pages have no automatic OCR. Tables in PDFs may lose layout.
- The optimizer sees development failures only. Holdout remains a small in-domain check, not an unseen-domain benchmark.
- Demo artifacts were inspected during development. Holdout is hidden from the in-run optimizer, not an untouched external benchmark of the development process.
- Corpus text and model call transcripts are stored locally in artifacts. Do not publish runs containing confidential input.
- Source prompt injection, model errors and incorrect tool arguments remain risks. Tools are read-only and bounded; no generated code is executed.
- Live date values depend on the run date. No external weather or paid service is required.
