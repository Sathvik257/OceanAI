# ForgeAI quality report

Run status: **completed**

Model: `qwen3-4b-instruct-2507`. Real local inference; 176 calls, 215963 reported/reserved tokens.

## Development evaluations

| Version | Passed | Rate | Selected |
|---|---:|---:|---|
| 1 | 14/18 | 77.8% | yes |
| 2 | 13/18 | 72.2% | no |

## Holdout (never used to choose patches)

4/6 passed (66.7%). This small, model-generated sample is not an estimate of production accuracy.

## Remaining observed failures

Recovery reused 67 exact recorded model responses; 109 calls were newly executed. See recovery.json. Reuse is not new inference; resource totals include prior usage and a conservative interrupted-request reservation.

- E03 (development, hallucination): The question asks whether supplier lead times are guaranteed to match specified arrival dates. The expected fact from the source explicitly states that lead times are 'estimates, not guaranteed arrival dates,' which directly addresses the question. The candidate refuses to answer and cites inability to verify evidence, despite having clear, direct evidence in the source. This refusal contradicts the expected status of 'answered' and fails to provide a correct factual response based on available evidence.
- E09 (development, hallucination): The question asks for specific information required to file a claim under a warranty policy, and the expected facts clearly state that the serial number and purchase-order reference are required. The candidate refuses to answer and cites inability to verify evidence, despite having access to a source (estuary.md) that directly states the required information. The refusal contradicts the expected status of 'answered' and fails to provide the required factual content, even though the evidence exists and is directly relevant. The candidate's response is not grounded in the available evidence and does not meet the expected facts.
- E15 (development, hallucination): The question asks for two specific pieces of information: (1) the required information to file a warranty claim for a sensor device, and (2) the email address to report a defective sensor item to Delta Field Supply. The expected facts confirm that the required claim information includes the serial number and purchase-order reference (from estuary.md), and that the defect report should include SKU, batch or serial number, and a description of the defect (from delta.md), with the email address being returns@delta.example. The candidate's answer correctly identifies that the email address is not explicitly stated in the documents, which is a factual limitation. However, the candidate fails to provide the required information (the email address) even though it is explicitly in the expected facts. The answer also incorrectly states that the warranty claim process applies only to specific devices (PH-30 probe and Logger L3), which is not supported by the evidence and contradicts the broader claim in the expected facts. Thus, the candidate does not meet the required factual coverage for the question.
- E16 (development, hallucination): The question asks for specific details required in an order to Estuary Instruments and the time frame for reporting defective items to Delta Field Supply. The expected facts clearly state that orders to Estuary Instruments must include SKU, quantity, delivery address, and purchase-order reference (from estuary.md), and that defective items must be reported within seven calendar days to Delta Field Supply (from delta.md). The candidate response incorrectly states that the defect reporting timeline is not explicitly stated and that procurement details are incomplete, despite the evidence in delta.md clearly supporting a seven-day reporting window. Moreover, the candidate refuses to answer, citing the need for clarification, even though the required facts are directly available in the cited documents. The candidate fails to report the correct, verifiable facts and instead introduces unsupported claims (e.g., 'absence of minimum order subtotal contradicts earlier mention') with no evidence. Thus, the answer does not correctly or fully address the expected facts, and the status 'clarify' is inappropriate given the availability of explicit, verifiable information in the sources.
- E05 (holdout, hallucination): The question asks whether the assistant should promise a specific arrival date when providing lead time information. The expected facts clearly state that 'Do not promise arrival on a specific date' (from delta.md), which directly addresses the behavior required. The candidate responds with a refusal and cites inability to verify evidence, which contradicts the expected status of 'answered' and fails to align with the explicit directive in the source. A refusal to answer when a clear directive exists is inconsistent with the expected behavior.
- E11 (holdout, hallucination): The question asks specifically when the quoted lead time starts according to Delta Field Supply's supplier conditions. The expected fact states that 'Written order acceptance starts the quoted lead time,' which directly answers the question. The candidate refuses to answer and cites inability to verify evidence, despite having a clear, directly supported fact in the provided source. This refusal contradicts the expected status of 'answered' and fails to provide the correct factual response even when the evidence is available.

## Changes and tradeoffs

- source_only: The failures are primarily due to the agent refusing to answer or providing incorrect information despite clear, direct evidence in the sources. The agent fails to ground responses in explicitly stated facts and instead introduces unsupported claims or refuses to answer when evidence exists. The 'source_only' patch ensures that all claims are strictly derived from quoted evidence, preserving accuracy, conditions, and numbers. This directly addresses the hallucination failures by enforcing that the agent must either provide verifiable, source-grounded answers or refuse only when no evidence supports a claim—preventing false refusals and incorrect inferences. Accepted: False; before 0.7778, after 0.7222.

## Limits of this evidence

- The same small model generates tests and supplies semantic judgments: correlated mistakes and self-preference remain possible. The judge sees no model identity or competing answer and receives no reward for verbosity; deterministic quote checks cannot establish semantic entailment.
- Expected facts are verified verbatim against sources; the questions, refusal labels and coverage claims still require human review. A wrong test oracle can distort scores.
- BM25 can miss paraphrases. PDFs need extractable text; scanned pages have no automatic OCR. Tables in PDFs may lose layout.
- The optimizer sees development failures only. Holdout remains a small in-domain check, not an unseen-domain benchmark.
- Demo artifacts were inspected during development. Holdout is hidden from the in-run optimizer, not an untouched external benchmark of the development process.
- Corpus text and model call transcripts are stored locally in artifacts. Do not publish runs containing confidential input.
- Source prompt injection, model errors and incorrect tool arguments remain risks. Tools are read-only and bounded; no generated code is executed.
- Live date values depend on the run date. No external weather or paid service is required.
