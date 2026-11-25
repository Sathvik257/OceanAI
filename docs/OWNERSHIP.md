# Candidate review before submission

This project was developed with AI assistance. The recruiter permits assistance but asks candidates to make original changes rather than submitting tool output unchanged. Do not claim this implementation was written without assistance. Do not invent manual work, test runs or personal reasoning.

Before submitting, make a real contribution you understand and record it honestly. Examples: improve a failure you can reproduce; design a new source corpus from your own interests and inspect its generated tests; add a failure mode with a justified check; or revise a design choice after comparing alternatives. Cosmetic edits alone are weak evidence of ownership.

## Explain it without reading the source

1. Trace one brief from input to requirements, generated agent, frozen tests, diagnosis, patch and report.
2. Explain why a correct quote does not prove a correct answer. Show one example.
3. Show an unsupported requested topic and where it is flagged.
4. Show why each attached tool is necessary. Explain what prevents an unattached tool from running.
5. Pick one failing evaluation. Decide whether the agent, retriever, test oracle or judge is wrong; do not assume the score is ground truth.
6. Explain why the holdout is useful and why six model-generated cases are still weak statistical evidence.
7. Show an accepted or rejected repair and any case regressions.
8. Run a new brief and folder, then load the resulting agent in the generic runner.
9. Explain the CPU/model tradeoff and what you would improve with more time.

## Your decisions and modifications

Fill this section in your own words after actually doing the work. It is intentionally not prewritten as if you had already made these decisions.

- A design decision I agree with, and why:
- A design decision I changed, and the evidence that motivated it:
- A failure I reproduced and investigated:
- What my change improved, and what it still does not solve:
- How I used AI assistance and how I checked its output:

## Submission gate

Do not call the project ready just because unit tests pass. Both demonstration `state.json` files must say completed; all required artifacts must exist; the actual scores and remaining failures must be read; the generic runner must work; and you must understand and adapt the implementation. Confirm the recruiter's submission format and exact deadline time separately.
