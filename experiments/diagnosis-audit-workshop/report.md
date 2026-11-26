# ForgeAI quality report

Run status: **completed**

Model: `qwen3-4b-instruct-2507`. Real local inference; 98 calls, 78183 reported/reserved tokens.

## Development evaluations

| Version | Passed | Rate | Selected |
|---|---:|---:|---|
| 1 | 14/18 | 77.8% | yes |

## Holdout (never used to choose patches)

5/6 passed (83.3%). This small, model-generated sample is not an estimate of production accuracy.

## Remaining observed failures

- E08 (development, hallucination): The question asks specifically for the access hours of the Riverside Tide Workshop on Saturday. The expected fact states clearly that it opens Saturday from 10:00 to 16:00, which directly answers the question. The candidate refuses to answer and cites inability to verify evidence, despite having a clear, directly cited source in the expected facts. This refusal contradicts the expected status of 'answered' and fails to provide the correct information even when it is explicitly available.
- E15 (development, hallucination): The candidate refused to answer the question and stated inability to verify evidence, despite clear evidence in the expected_facts supporting both parts of the question: (1) a separate laser induction and current endorsement are required beyond general induction, and (2) a current laser endorsement does not eliminate the need for a duty steward. The expected_status is 'answered', and the candidate's refusal contradicts the availability of direct, cited evidence. The answer fails to address the factual query and does not provide the required information.
- E16 (development, hallucination): The candidate refused to answer the question and stated that evidence could not be verified, despite clear, directly relevant facts in the expected_facts list (e.g., medical information must not be included and card lending is not permitted). The expected_status is 'answered', and the candidate's response fails to provide a correct or grounded answer, instead refusing based on lack of verification when the facts are explicitly available in the provided sources. The answer does not match the expected status or provide the necessary factual response.
- E21 (development, hallucination): The question 'How much does it cost?' is vague and lacks context (e.g., what item, service, or scenario?), so a refusal to answer is appropriate. The candidate correctly refuses to answer without sufficient context, which aligns with the expected status of 'clarify'. However, the expected status is 'clarify', not 'refused', and the candidate's response does not attempt to clarify the question—instead, it refuses outright. A proper response under 'clarify' would ask for more details. Thus, while the refusal is reasonable, it does not match the expected status of 'clarify'.
- E22 (holdout, hallucination): The question 'When will it happen?' is vague and lacks context, making it impossible to determine a specific event or timeframe. The candidate correctly refuses to answer without clarification, as the question does not specify what 'it' refers to. The expected status is 'clarify', not 'refused', so the behavior is incorrect. Although the refusal is cautious, it does not match the expected status of 'clarify'.

## Changes and tradeoffs

- stop: The critic proposed a patch with no matching diagnosed failures; no change applied. Accepted: False; before 0.7778, after None.

## Limits of this evidence

- The same small model generates tests and supplies semantic judgments: correlated mistakes and self-preference remain possible. The judge sees no model identity or competing answer and receives no reward for verbosity; deterministic quote checks cannot establish semantic entailment.
- Expected facts are verified verbatim against sources; the questions, refusal labels and coverage claims still require human review. A wrong test oracle can distort scores.
- BM25 can miss paraphrases. PDFs need extractable text; scanned pages have no automatic OCR. Tables in PDFs may lose layout.
- The optimizer sees development failures only. Holdout remains a small in-domain check, not an unseen-domain benchmark.
- Corpus text and model call transcripts are stored locally in artifacts. Do not publish runs containing confidential input.
- Source prompt injection, model errors and incorrect tool arguments remain risks. Tools are read-only and bounded; no generated code is executed.
- Live date values depend on the run date. No external weather or paid service is required.
