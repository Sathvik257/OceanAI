# Reviewing and demonstrating ForgeAI

These are technical study notes, not a script for claiming work or experience you did not do. Run the commands yourself and use your own explanation.

## Start with evidence

Open a completed run's `state.json`, then `report.md`. Identify the selected version and read a failure, not just the headline score. Open its scorecard and follow the case from retrieved chunks through the raw response, runtime guard and judge verdict. Compare the judge's explanation with the source yourself.

The strongest explanation is concrete: "This question failed because the expected source chunk was not retrieved," or "The quotation was real, but the answer added an unsupported claim." Do not call every failed score a hallucination.

## Show the two agents behaving differently

With the reference model server running:

```powershell
.venv\Scripts\python -m forgeai chat --agent artifacts/workshop/agent.json --question "If I cancel exactly 24 hours before my session, is the booking fee refunded?"
.venv\Scripts\python -m forgeai chat --agent artifacts/workshop/agent.json --question "May I bring a guest on Saturday?"
.venv\Scripts\python -m forgeai chat --agent artifacts/coastal/agent.json --question "What is the item subtotal for three CT-10 probes, excluding tax and shipping?"
```

Expected behavior from the fictional documents: the cancellation qualifies for a full booking-fee refund; guest admission is not specified and must not be invented; three CT-10 probes have an item subtotal of INR 14,400. These are review expectations, not assertions that a particular model run passed them. Inspect actual outputs and tool traces.

Check the definitions. The workshop brief needs no registry tools. The procurement brief needs exact CSV lookup and arithmetic. A tool is not justified merely because it might be useful someday.

## Explain the factory, not only the chat

1. The brief is parsed separately from the documents so unsupported requests cannot quietly disappear.
2. Topic coverage needs a verifiable source quotation. Missing support stays visible in requirements.
3. The generator creates a data definition. It never generates Python that the runner executes.
4. The evaluator generates questions and quoted expected facts from the input corpus. It rejects fabricated quotations.
5. Development cases guide small repairs; holdout cases do not influence patch selection.
6. The selected agent and every attempted version remain inspectable, including non-improving changes.

## Be ready for these questions

**Why not use embeddings?** BM25 avoids a second model and works well for exact product identifiers and policy terms. It is weaker on paraphrases. A hybrid retriever would be an extension to measure, not a performance claim already established here.

**Does a valid citation make an answer grounded?** No. The quote can be genuine while the conclusion is false. That is why source validation and semantic judgment are separate, and why the judge itself was audited.

**Can the model write easier tests to make itself look good?** Yes. The fixed suite, expected-source checks and holdout reduce some risks, but the same model still generates the oracle and judges answers. Inspect test diversity and labels. A separate human-labeled benchmark would be stronger.

**Why only three versions?** The assignment caps the loop. Each transition changes one diagnosed behavior, and the score must improve to replace the selected agent. The report also exposes regressions hidden by an aggregate increase.

**What if the brief asks for missing information?** The factory should flag it in requirements and constrain the generated agent. It should not turn a related passage into permission to invent a missing rule.

**What does the score mean?** It is the fraction of this generated suite that passed the stated guards and model rubric. It is not production accuracy, a confidence interval, or a guarantee on unseen briefs.

**What happens if the model fails?** Malformed structured responses get a bounded retry. A malformed evaluation response remains a failed case. Network or budget failures stop the run with an incomplete status. There is no hidden mock fallback.

## Rehearse an unfamiliar input

Use two small documents from a domain you understand. Write a paragraph asking for both supported topics and one deliberately missing capability. Use a fresh output directory. Read the requirements before looking at the final scores. If the factory misunderstands the brief or invents coverage, document that failure rather than editing the artifacts to hide it.

Finish the personal review in `OWNERSHIP.md` after making and verifying a real change. Confirm the recruiter's exact submission format and deadline time; neither is established by these technical notes.
