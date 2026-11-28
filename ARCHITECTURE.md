# Anticipatory Commerce agent: architecture

**Team Claudus, Masters' Union · AgentX Challenge 1 · `agent.py`, Python standard library only**

**Goal.** Words arrive one at a time. Show the right product as early as possible, and never show the wrong one.
A wrong commit costs **−1.0**, while earliness can add at most **+0.6** and each extra search costs **−0.02**. So the agent is built to be **certain before it speaks**.

```
word ─► 1 PARSE ─────────► 2 GAUGE ───────────► 3 RISK GATE ────────► 4 COMMIT ──► finish(): 5 VERIFY
        bilingual slots     facet counts:         correction cues,      ONE counted   committed product still meets
        last mention wins   "how many products    clause boundaries,    search, k=2   every final filter? yes → done
        pending flags       still fit?"           pending slots                       no → one search
```

1. **Parse.** Each word, a deterministic parser re-reads the request and fills five slots: category, colour, size, brand and max price.
   - **Vocabulary.** Catalogue values plus about 150 shopper synonyms (*runners, floaters, lowers, denims, bag pack, kicks, frock, headset*), Hindi colours (*kaala, laal, gulabi, bhura*) and size phrasing (*double XL, UK nine, 32 waist, das number*).
   - **Numbers.** A spoken-number reader handles *forty five hundred, three and a half k, 0.8k, ₹1,500, saadhe teen hazaar, dedh hazaar, pandrah sau se kam*. Context decides whether a number is a price or a size.
   - **Corrections.** The **last mention wins** ("black, oops, grey" → grey; "Northweft, or rather Tanaro" → Tanaro). Hindi post-negation ("M size nahi, small") and English pre-negation ("not red") are both handled.
   - **Pending slots.** A slot that may still change is never used to commit: a number mid-utterance, "navy" before "blue", "extra" before "large".
   - **Ambiguity.** "Trainers" keeps both readings (running shoes and sneakers), and the catalogue decides which product exists.
2. **Gauge.** A facet-count model built offline from `catalogue.csv` maps every combination of category, colour, brand and size to its prices. It answers "how many products still fit?" in O(1) and stores **no product IDs**, so every product shown comes from a counted search.
3. **Risk gate.** Commit only when (a) exactly one product fits the stable slots, (b) nothing is pending, (c) no correction cue (*sorry, wait, actually, make that, nahi, matlab, or rather*) has opened since the last slot value, and (d) the current word is not a clause boundary ("size M**.**") or a hedge (*I, only, um*), which is where corrections start.
4. **Commit** with a single search (`k=2`, so the store itself confirms the product is unique).
5. **Verify** at `finish()`. If the committed product satisfies every final filter, it is **provably** the only match: it was unique under fewer constraints, and the target satisfies all of them. Late constraints therefore cost **zero** extra searches.

## Results on `dev.jsonl` (300 requests)

| | Baseline | Ours |
|---|---|---|
| **Score** | 20.0 | **46.6** (ceiling ≈ 49.8) |
| Accuracy | 52.7% | **100%** |
| Wrong commits | 0 | 5 (mid-sentence corrections after a unique match) |
| Earliness | 0% | **13.9%** of the request (best possible 16.3%) |
| Searches / request · latency | 1.53 · – | **1.02 · 0.2 ms/word** |

By tag: plain 49.5 · code-mixed 52.0 · late constraint 45.4 · correction 36.5.
On **fresh wording we never tuned on** (written by a separate local LLM and by hand, labels checked against the catalogue) it reached **91% accuracy with 0 wrong commits**; most misses were label noise.

**Cost and scale.** There is no LLM at run time: ₹0 per request, and about 200 requests per second on one CPU core. A new catalogue only needs a rebuild of the vocabulary and facet table, which takes milliseconds.
`AGENT_MAX_SEARCHES` caps search spend, and one constant trades earliness against wrong-commit risk.
