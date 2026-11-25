# Build and acceptance plan

The product is an agent factory, not a domain-specific chatbot. Its input is an unfamiliar brief and document directory. Its deliverable is a portable definition plus evidence.

1. Ingest PDF, Markdown, text and CSV with stable source/chunk identifiers and hashes. Reject unreadable inputs explicitly.
2. Let a small open model extract requirements, propose up to five questions and identify unsupported requirements. Unattended mode records assumptions instead of waiting for input.
3. Generate a declarative agent with retrieval settings, a restricted tool allowlist and a strict answer contract.
4. Generate at least 20 evaluation cases from supplied evidence. Validate quoted facts against the corpus before accepting cases. Freeze a development/holdout split before optimization.
5. Combine deterministic citation/quote checks with an isolated model judge. Grade factual coverage, appropriate refusal and ambiguity handling separately. Do not equate citations with truth.
6. Run at most three evaluated versions. Apply small diagnosed changes; log rejected and accepted changes, regressions, scores and unresolved failures.
7. Preserve model calls, runtime configuration, corpus hashes, definitions, requirements, evaluations, scorecards and reports. Never label a mock execution as a real demo.
8. Exercise the generic runner and two contrasting demos. Add adversarial tests for malformed model output, unsupported requirements, citation fabrication, tool access and budget exhaustion.
9. Review results critically, document limitations, and prepare an ownership walkthrough for the candidate.

Submission remains pending until real demonstrations are complete and the candidate has reviewed, modified and understood the work in accordance with the recruiter's originality instruction.
