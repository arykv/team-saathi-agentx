# Abstract: Anticipatory Commerce agent (Team Claudus, Masters' Union)

We built a shopping agent that finds the product before the shopper finishes speaking, and that would rather wait one more word than show the wrong thing.
On the public dev set it scores **46.6 against the baseline's 20.0** (the ceiling is ≈49.8). It gets **100% of final answers right**, uses **1.02 searches per request** and takes **0.2 ms per word**.

**Impact.** Indian shoppers mix English and Hindi, change their minds mid-sentence and add constraints late:
*"mujhe kaala Urbanyx jacket budget saadhe teen hazaar, M size milega?"* The baseline gets half of such requests wrong.
Our agent reads them and commits to the right product **14% of the request early** on average (the best possible is 16%).
A wrong commit is the costliest error, so we tuned for trust: on fresh wording written outside our team it made **zero wrong commits**.

**Innovation.**
1. **Facet-gated commitment.** A facet-count model built offline from the catalogue answers "how many products still fit?" in microseconds while storing no product IDs.
   The agent spends its single search only when exactly one product remains, so the store itself confirms every product shown.
2. **Provable zero-cost verification.** If the committed product still satisfies every final filter, it must be the unique match. Late constraints cost no extra search; only a contradicting correction triggers one.
3. **Listening for corrections.** Values that could still change are marked pending: a number mid-utterance, "navy…" before "blue", "extra…" before "large".
   The risk gate also holds back at clause boundaries and correction cues ("oops", "actually", "or rather", "nahi", "matlab"), where corrections begin. Because the last mention wins, "black, oops, grey" resolves itself.
4. **Ambiguity left to the catalogue.** "Trainers" keeps both readings (running shoes and sneakers), and one search settles which product exists.
5. **Bilingual numbers and sizes:** *dedh hazaar, pandrah sau se kam, forty five hundred, 0.8k, double XL, das number, 32 waist.*

**Build summary.** `agent.py` is about 530 lines of pure Python: standard library only, no model weights, no API keys.
Per word it parses five slots, checks the facet model, applies the risk gate, and commits with one counted search.
Scores by tag: plain 49.5, Hinglish 52.0, late constraint 45.4, correction 36.5.
We tested robustness on wording we never tuned on, written by a separate local LLM and by hand.

**Cost estimate.** There is no LLM in the hot path, so marginal cost is about **₹0 per request**.
One CPU core handles about 3,300 words per second (about 200 requests per second), so a single ₹800/month cloud VM serves well over 100 million requests a month.
A new catalogue needs only a rebuild of the vocabulary and facet table, which is milliseconds per thousand products.

**Feasibility and scale.** The agent drops into any storefront search box or voice assistant as a pre-fetcher. One constant trades earliness against safety, so a retailer can choose "faster" or "never wrong", and `AGENT_MAX_SEARCHES` caps search spend.
