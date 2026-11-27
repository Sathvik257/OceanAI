# Observations from actual development

## Intake: real model omission

The first local Qwen2.5 1.5B run read the brief and corpus in one request. It produced plausible requirements, but omitted the explicit weekend guest-access gap and the brief's refusal topics. It also proposed questions whose answers were already in the documents. This was a real failure, not a simulated example.

The run was interrupted before evaluation. Its raw call and requirements remain in `experiments/intake-v1/`; its state explicitly says it was interrupted. It is not counted as one of the required demonstrations.

The fix separates brief-only intent extraction from per-topic document support assessment. Supported coverage now needs a verifiable quote rather than just a valid document ID. Unsupported requested topics remain visible and become refusal boundaries. This is conservative: retrieval failure can still cause a false gap, which must be acknowledged in the report.

Unit tests passed before this failure. That is why the actual local-model runs and manual review matter more than a green test count.

## Coverage: contradictory verdicts and distracting context

Both the 1.5B and 3B models struggled when a single prompt had to select evidence and judge support among several excerpts. In one 3B diagnostic, the model quoted the actual opening hours but still claimed that no hours were specified. A concrete example in the earlier prompt also biased attention toward a neighboring topic.

Minimal probes with a single relevant sentence succeeded. The pipeline therefore separates exact passage selection from a second, short support decision over that passage. The quote must pass deterministic source validation before the second model call. Explicit prohibition clauses are also preserved directly from the brief rather than relying entirely on extraction.

The diagnostic traces under `experiments/model-comparison/` are retained, including the failures. Model size alone was not a sufficient fix; task decomposition and prompt design mattered.

## Runtime profiling

The laptop's Intel Iris Xe GPU supports the portable Vulkan backend. A short benchmark showed roughly nine times faster prompt processing than the CPU configuration. Generation improved less. The reference demonstrations use Vulkan; CPU remains a supported, slower fallback. No system drivers or other applications were modified.

## Judge audit and model selection

The older 3B judge rejected a correct answer at an inclusive threshold: exactly 24 hours qualifies under an "at least 24 hours" cancellation rule. The newer Qwen3 4B model initially returned the correct booleans but a contradictory explanation on that probe. The judge contract was changed to explain the comparison before emitting verdicts, and the rubric now explicitly evaluates the exact question rather than a stronger claim the answer never made.

The added-invention probe's correctness label was clarified from "contains the expected fact" to "the whole answer is correct", consistent with the final rubric's rejection of unsupported additions. The original audit and label are retained under `experiments/judge-calibration-4b-initial/`. The final audit agrees with all five labeled probes. These are development diagnostics used to improve the rubric, not independent test accuracy. The final agent holdout is separate.

## Evaluation generation: repeated broad questions

The first 4B workshop run reached evaluation generation, but repeated broad questions about the same topics despite duplicate feedback. The validator stopped instead of pretending the required suite existed. That run is preserved under `experiments/batch-evals-workshop/`; the accompanying coastal run was interrupted when its execution session ended.

The replacement generator samples distinct verbatim facts from all source documents first, then asks the local model for one focused question per fact or cross-document fact pair. The code supplies the source references and expected quotations directly from the corpus. The model still writes every question. This reduces copied answer-key errors, discourages repetitive tests, and substantially reduces the amount of text the small model must generate. Draft suites are checkpointed and still never count as complete evaluations.

## Cross-document oracle audit

Inspecting the next generated suite found a two-source case whose question addressed only one expected fact. That would penalize a correct answer for failing to answer an unasked question. The run was stopped and retained under `experiments/cross-document-audit-workshop/`. Cross-document cases now compose two separately generated source-specific questions and retain those subquestions for inspection. Similar restatements are excluded from candidate pairs. This checks question coverage structurally, but does not prove semantic quality; reviewers should still inspect the question and both quotations.

## Isolated tool selection

Combining prompt drafting and tool explanations confused the small model about selected versus rejected tools. A short isolated selection probe correctly returned no tools for workshop policy questions and CSV lookup plus calculator for procurement. The factory now uses that separate selection step, validates registry names and CSV availability, and supplies the resulting allowlist to the prompt generator. The probe is a development observation, not evidence of universal tool-selection accuracy.

## Refusal and ambiguity label audit

The next manual audit found clear policy questions labeled as ambiguous and a refusal case asking whether an expired endorsement allowed booking. That is an answerable policy question, not a request for prohibited assistance. The run was stopped; its artifacts remain in `experiments/label-audit-workshop/`.

The generator now uses separate prompts for positive, refusal and ambiguity cases. Ambiguity prompts receive no source facts and vary cost, timing, eligibility and availability while deliberately leaving a pronoun unresolved. Refusal prompts request the prohibited assistance directly rather than asking whether it is permitted. A separate case asks for unavailable private credentials. Length, pronoun, request-form and duplicate checks catch some mistakes, but these are limited structural checks, not proof of correct semantic labels. The small-model probes are retained alongside the failures.

## Bounded topic coverage versus exhaustive coverage

The first coastal intake rejected a documented five-working-day lead time because one quotation did not describe every requested item. Adding the complete SKU row alone did not fix that interpretation. Both failures are preserved in the coastal coverage diagnostics.

The support rubric now asks whether the verified passage and its source context support a bounded factual answer on the topic. It does not treat one row as proof of a complete catalogue. A local positive probe accepts the documented TP-20 lead time; a separate negative probe still rejects live stock because the documents explicitly say it is unavailable. The support method and its limits are recorded in requirements. This intake correction followed the completed workshop demonstration; each run's implementation snapshot identifies its actual source version.

A subsequent assessment selected a warning that item subtotals are not final payable totals, even though a unit-price row was already retrieved. The guard now tries at most two alternative passages after a verified but insufficient quotation, preferring a different document format when available. It stops on supported evidence, invalid quotes, or explicit missing-information statements. Every assessment is retained in the requirements' `attempts` list. The unchanged first ten real model requests were reused through exact-prefix recovery; the complete preceding attempt and copied-prefix provenance are retained.

An excerpt-selection retry still returned an empty string for a price row. The fallback therefore supplies the complete bounded source chunk verbatim to the support judge, avoiding a second lossy extraction step. A real local probe recognized that the CT-10 row's INR 4800 unit price supports a subtotal when a user supplies the quantity. It does not grant tax, shipping, or live inventory capabilities.
