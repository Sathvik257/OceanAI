# Secondary evidence review

These observations were made during AI-assisted development by inspecting saved artifacts. They are not an independent human benchmark. The candidate should check them against the source documents before submission.

## Workshop: citation fidelity can reject a correct fact

In the completed baseline under `experiments/diagnosis-audit-workshop/`, E08 asks for Saturday access hours. The raw answer correctly gives 10:00–16:00. Its purported quotation is “The Riverside workshop opens Saturday from 10:00 to 16:00.” The actual source says “It opens Saturday from 10:00 to 16:00.”

The quotation-occurrence guard rejects that rewritten sentence, replaces the visible answer with a refusal, and retains both the raw answer and guard error in the scorecard. The factory classifies the failed citation as `hallucination`, one of the four assignment categories. This should not be described as inventing the opening hours: it is a citation-fidelity failure. Strict quotation checking trades some useful answers for inspectable evidence.

The automatic judge sees the guarded refusal and correctly records that it failed to answer a supported question. Its explanation alone does not reveal why the guard refused, so inspect `raw_response` and `guard_errors` as well as the judge verdict.

## Diagnosis must preserve the reason for a guard failure

That baseline completed at 14/18 development and 5/6 holdout. Its empty refusals were incorrectly grouped with citation errors as hallucinations. The critic proposed a refusal repair, but the category check rejected it. This was a factory defect, not merely weak model performance.

The subsequent correction distinguishes citation violations, missing retrieval, raw refusals and other output-contract failures. The critic receives only repairs relevant to observed categories. The answer schema also requires a nonempty answer string. The baseline is retained unchanged; its scores are not presented as results of the corrected implementation. A targeted development probe and fresh runs provide separate evidence for the changes.

## The judge can approve the wrong behavior

In `artifacts/workshop/scorecard.v1.json`, E15 asks two supported questions about laser induction and steward presence. The agent refuses. The local judge nevertheless sets all three semantic criteria to true and calls the refusal justified, even though the supplied expected status is `answered`.

The final case result is still a failure: the independent status comparison is false and cannot be overridden by the judge. This is concrete evidence for combining deterministic checks with model judgments. It also shows why agreement on five calibration probes must not be presented as general judge reliability.

## Coastal: residual oracle and coverage risks

Before scoring the coastal suite, E09 was flagged as potentially underspecified: it asks what information a sensor warranty claim needs without naming the supplier, while its expected fact comes from Estuary's policy. A supplier-specific explanation or clarification may be reasonable. The frozen score still includes this case; it is not silently relabeled or excluded to improve results.

The coastal coverage assessment also describes working-day lead times as a compatibility limitation. That rationale is not a reliable compatibility proof. Actual compatibility values are available in the CSV, so admitting the topic is reasonable, but the selected quotation and explanation are weak evidence. This is another example of why quote occurrence and a model's fluent explanation do not establish semantic correctness.
