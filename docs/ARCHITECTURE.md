# Decisions worth defending

## Why an explicit pipeline?

The task asks for autonomy under imperfect model outputs. Autonomy does not require arbitrary code generation or an unconstrained multi-agent conversation. A state machine makes stage boundaries, failure handling, budgets and artifacts visible. The model still performs semantic work: requirements, agent design, test generation, answer construction, judging and patch selection.

## Evidence has two layers

The code proves that a quote occurs in a retrieved source. It does **not** prove that the quote supports the answer. A semantic judge checks that second question. A real citation plus an invented conclusion must fail. The raw answer is retained even when the runtime guard changes the visible response into a refusal.

## Why BM25 instead of embeddings?

It starts offline, requires no second model, performs well on policy terms and exact SKUs, and is easy to diagnose. The tradeoff is paraphrase sensitivity. Retrieval misses are distinguished from wrong refusals so a retrieval patch can increase context or source diversity without rewriting the agent. For a larger corpus, an embedding index and hybrid retrieval would be a measured extension, not a prerequisite.

## Why quote-based expected facts?

An evaluation generator can hallucinate its answer key. Requiring verbatim facts and valid source IDs catches many fabricated or distorted keys before scoring. It does not validate the question's logic or prove a refusal label. Those are explicitly residual risks. Source hashes detect changed documents; frozen evaluation hashes help ensure the optimizer did not move the goalposts.

## Why a holdout?

Eighteen development cases can influence repair. Six stratified holdout cases are scored once after selection. The same generator and source corpus create both, so this is protection against direct test-fitting rather than an independent benchmark. An unseen domain supplied by a reviewer is the stronger generalization check.

## Judge bias controls

- Single anonymous answer, no side-by-side preference contest: removes ordinary candidate-position bias.
- Fixed factual criteria and expected evidence: verbosity earns no score by itself.
- No model name in judge input: reduces explicit self-preference cues.
- Deterministic citation/status gates: a generous judge cannot overrule fabricated evidence.
- Raw judgments and explanations preserved: a reviewer can disagree with or rescore them.

These controls reduce failure modes; they do not establish an unbiased judge. A separately trained judge model or human-labeled audit would provide stronger independence.

## Bounded repair

Maximum three evaluated versions, including the initial definition. One targeted patch per transition. Allowed changes are increased retrieval depth, document diversity, source-only constraints, more precise refusal behavior, and clarification/coverage instructions. No expected answer, question string or source-specific fact enters the repaired prompt. Strictly improved development score is required to replace the selected definition; ties keep the earlier version. Any aggregate improvement can still hide case regressions, which are listed.

## Security and portability

Definitions are data, not executable Python. The calculator uses a bounded AST allowlist. CSV paths stay inside the packaged source directory. Tool calls are checked against attached permissions. The agent package includes its source snapshot and checks hashes on load. There is no shell tool, arbitrary HTTP tool, or generated code execution. Documents remain untrusted model input; prompt injection cannot be claimed solved by wording alone.
