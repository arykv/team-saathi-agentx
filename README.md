# AgentX Challenge 1: Anticipatory Commerce · Team Claudus

A shopping agent that reads a request one word at a time and shows the right product the moment it is certain.
It never guesses: a wrong product costs more than being early earns.

| on `dev.jsonl` (300 requests) | Baseline | **Ours** |
|---|---|---|
| Score | 20.0 | **46.6** (ceiling ≈ 49.8) |
| Accuracy | 52.7% | **100%** |
| Earliness | 0% | **13.9%** of the request (best possible 16.3%) |
| Searches per request | 1.53 | **1.02** |
| Latency | — | **0.2 ms per word** |

## Run it

Python 3.9+, standard library only. Nothing to install, no API keys.

```bash
python evaluate.py --agent agent.py                              # score on dev.jsonl
python evaluate.py --agent agent.py --log results/dev_results.jsonl
python evaluate.py --agent agent.py --data tests/fresh_wording.jsonl   # wording we never tuned on
python demo/server.py                                            # live demo at http://localhost:8790
```

`agent.py` finds `catalogue.csv` next to itself, next to the harness's `search.py`, or in the working directory.
Set `AGENT_MAX_SEARCHES` to cap searches per request (default 3; it uses about 1.02).

## Files

| File | What |
|---|---|
| `agent.py` | The agent: bilingual slot parser, facet-count model, risk gate, single-search commit, zero-cost verification |
| `ARCHITECTURE.md` | One-page architecture note |
| `ABSTRACT.md` | Round 1 abstract (under 500 words) |
| `results/` | `--log` output and summaries on `dev.jsonl` and on the fresh-wording set |
| `tests/` | Hand-written hard cases and fresh-wording requests (labels checked against the catalogue) |
| `tools/` | Parser check, the fresh-wording validator, and the local-LLM paraphrase generator |
| `demo/` | Live demo: type or speak, and watch every word's decision, candidate count, searches and latency |
| `evaluate.py`, `search.py`, `catalogue.csv`, `dev.jsonl` | Unchanged from the official starter kit |

## How it works

See [ARCHITECTURE.md](ARCHITECTURE.md). In short:
1. Parse the words so far (the last mention wins, so corrections resolve themselves) and mark slots that may still change.
2. Ask the facet model how many products still fit. It is built offline and stores counts only, no product IDs.
3. When exactly one fits and no correction is open, run **one** search and commit.
4. At the end, if the committed product satisfies every final filter, it is provably the only match: no second search is needed.
