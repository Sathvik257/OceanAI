# Assignment traceability

| Mandatory requirement | Implementation | Evidence to inspect |
|---|---|---|
| 1. Intake interviewer, at most five questions | `factory.intake`, brief extraction, per-topic inspection, optional CLI interview | `requirements.json`: scope, audience, tone, questions, answers and assumptions |
| 2. Groundability guard | Per-topic retrieval, model support decision, exact quote/ID validation; unsupported topics become gaps/refusals | Coverage entries and deliberate missing-topic behavior |
| 3. Complete declarative agent generator | `factory.make_definition` | System prompt, chunking, BM25 parameters, registry allowlist and output contract in `agent.json` |
| 4. Generated evaluation set, at least 20 cases | `evaluation.generate_evals`; 24 accepted cases across four categories | `evals.json`, generation prompts, raw model calls, rejected generation cases |
| 5. Automated judge with bias controls | `evaluation.score_case`, deterministic evidence validation and criterion-based local judge | Per-case dimensions, reasons and separate diagnostic calibration |
| 6. Targeted critic/optimizer, maximum three iterations | `factory.propose_patch` and bounded build loop | Versioned definitions, scorecards, changes with before/after scores and regressions |
| 7. Honest reporting | Incremental state and scorecards; final report even after a failure or exhausted budget | `state.json`, `report.md`, `usage.json`; no completeness claim for interrupted runs |
| 8. Runnable generic product | `forgeai chat --agent ...` | Actual single-question and dialogue execution against any valid packaged definition |
| 9. Two complete contrasting demonstrations | Workshop policies and coastal sensor procurement | Both complete artifact directories and independent artifact verifier |

The table identifies where to verify each requirement; it is not itself proof that a demonstration completed. The committed run states and real model traces are the evidence. Candidate review and original modifications remain required by the recruiter's separate instructions.

## Optional features deliberately prioritized

Budget enforcement and a sealed holdout improve the mandatory factory's reliability. A prompt tournament, hosted UI, hand-written human baseline and regression mode are not claimed. The provided runner is a CLI, which satisfies the mandatory runnable-product requirement.
