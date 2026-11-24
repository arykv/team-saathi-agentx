"""Team Saathi: anticipatory shopping agent for AgentX Challenge 1.

    python evaluate.py --agent agent.py

How it works, per word:
  1. Parse:   re-read the request so far with a deterministic, bilingual (English and Hinglish)
              slot parser. Later mentions override earlier ones, which handles corrections
              ("black, oops, grey"). A slot whose value may still be changing (a number still
              being spoken, "navy" that may become "navy blue", "extra" that may become
              "extra large") is marked pending.
  2. Gauge:   a facet-count model, built offline from catalogue.csv, says how many products the
              stable slots still allow. It holds counts only, never product IDs, so every product
              the agent shows comes from a counted search.
  3. Commit:  when the facets allow exactly one product and a risk check passes (no correction
              cue in the last few words, nothing pending), run ONE search and show the shopper
              that product.
  4. Verify:  at the end, re-parse the full request. If the committed product still satisfies
              every final filter, it is provably the only match, so no second search is needed.
              If it does not (a correction arrived later), search once with the final filters.
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _find_catalogue():
    """Next to this file, else wherever the harness's search.py reads it from, else the working dir."""
    candidates = [HERE / "catalogue.csv"]
    try:
        from search import CATALOGUE_PATH
        candidates.append(Path(CATALOGUE_PATH))
    except Exception:
        pass
    candidates.append(Path.cwd() / "catalogue.csv")
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("catalogue.csv not found next to agent.py or search.py")


CATALOGUE = _find_catalogue()

# --------------------------------------------------------------------------------------
# Vocabulary. Catalogue values are canonical; the rest are synonyms seen in shopper speech.
# --------------------------------------------------------------------------------------

CATEGORY_PHRASES = {
    # multi-word phrases first: they are matched longest-first
    "running shoes": ["running shoes", "running shoe", "running sneakers", "running sneaker", "jogging shoes",
                      "jogging shoe", "runners", "runner", "running trainers", "jogging sneakers", "road runners",
                      "running"],
    "sneakers": ["casual shoes", "casual shoe", "casual sneakers", "casual sneaker", "sneakers", "sneaker",
                 "kicks", "lifestyle shoes", "canvas shoes", "everyday shoes", "street shoes"],
    # Ambiguous words keep every reading; the catalogue decides which one exists.
    ("running shoes", "sneakers"): ["trainers", "trainer", "sports shoes", "sport shoes", "shoes", "shoe",
                                    "footwear", "joote", "jootey", "juta", "jutey", "gym shoes"],
    "sandals": ["sandals", "sandal", "slides", "slide", "floaters", "floater", "flip flops", "flip-flops",
                "flipflops", "slippers", "slipper", "chappals", "chappal", "sliders", "slider", "chappal"],
    "hoodies": ["hooded sweatshirts", "hooded sweatshirt", "hoodies", "hoodie", "hoody", "hooded jacket",
                "hooded top", "sweatshirt", "sweatshirts"],
    "t-shirts": ["t-shirts", "t-shirt", "t shirts", "t shirt", "tshirts", "tshirt", "tees", "tee", "tee shirt",
                 "tee-shirt", "teeshirt"],
    "shirts": ["casual shirts", "casual shirt", "formal shirt", "formal shirts", "shirts", "shirt", "button down",
               "button-down"],
    "track pants": ["track pants", "track pant", "trackpants", "trackpant", "joggers", "jogger", "lowers",
                    "lower", "sweatpants", "sweat pants", "track bottoms", "trackies", "tracks"],
    "jeans": ["pair of jeans", "pairs of jeans", "jeans", "jean", "denims", "denim", "denim jeans"],
    "jackets": ["jackets", "jacket", "bomber", "windcheater", "windbreaker", "blazer", "coat", "puffer"],
    "dresses": ["dresses", "dress", "frock", "frocks", "gown", "gowns", "one piece", "one-piece"],
    "kurtas": ["kurtas", "kurta", "kurtis", "kurti", "kameez"],
    "backpacks": ["backpacks", "backpack", "back pack", "bag pack", "bagpack", "bagpacks", "rucksack",
                  "rucksacks", "school bag", "college bag", "laptop bag", "bag"],
    "caps": ["caps", "cap", "baseball cap", "hat", "hats", "topi"],
    "headphones": ["headphones", "headphone", "headset", "headsets", "earphones", "earphone", "ear phones",
                   "over-ear", "over ear"],
    "watches": ["wrist watches", "wrist watch", "wristwatches", "wristwatch", "watches", "watch", "ghadi",
                "timepiece"],
    "wallets": ["wallets", "wallet", "purse", "purses", "billfold", "card holder", "money clip"],
}

COLOUR_PHRASES = {
    "navy": ["navy blue", "navy", "dark blue", "neela navy"],
    "olive": ["olive green", "olive", "army green"],
    "black": ["black", "kaala", "kala", "kaali", "kali", "jet black"],
    "white": ["white", "off white", "off-white", "safed", "safaid", "sufaid", "safedh"],
    "grey": ["grey", "gray", "charcoal", "slate", "saleti", "silver grey"],
    "blue": ["blue", "neela", "nila", "neeli", "nili", "sky blue", "royal blue"],
    "red": ["red", "laal", "lal", "crimson"],
    "maroon": ["maroon", "burgundy", "wine", "mehroon", "maroon red"],
    "green": ["green", "hara", "hari", "harا", "hare"],
    "beige": ["beige", "cream", "khaki", "sand"],
    "brown": ["brown", "bhura", "bhoora", "bhuri", "chocolate", "coffee"],
    "yellow": ["yellow", "peela", "pila", "peeli", "pili", "mustard"],
    "pink": ["pink", "gulabi", "rose"],
    "tan": ["tan", "camel"],
    "gold": ["gold", "golden", "sunehra", "sunehri"],
    "silver": ["silver", "chandi", "chaandi"],
}

LETTER_SIZES = {
    "xs": "XS", "s": "S", "m": "M", "l": "L", "xl": "XL", "xxl": "XXL", "2xl": "XXL",
    "small": "S", "medium": "M", "large": "L", "med": "M", "sm": "S", "lg": "L",
    "x-small": "XS", "x-large": "XL", "xx-large": "XXL", "extra-small": "XS", "extra-large": "XL",
}
SIZE_PHRASES = {
    "extra small": "XS", "extra large": "XL", "double xl": "XXL", "double extra large": "XXL",
    "xx large": "XXL", "x large": "XL", "x small": "XS", "double x l": "XXL",
    "extra extra large": "XXL", "2 xl": "XXL",
}

# English and Hindi number words
UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    # Hindi / Hinglish
    "ek": 1, "do": 2, "teen": 3, "tin": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6,
    "chhah": 6, "chah": 6, "che": 6, "saat": 7, "sat": 7, "aath": 8, "aat": 8, "nau": 9, "das": 10,
    "dus": 10, "gyarah": 11, "gyaarah": 11, "barah": 12, "baarah": 12, "terah": 13, "chaudah": 14,
    "pandrah": 15, "pandrah": 15, "pandra": 15, "solah": 16, "sola": 16, "satrah": 17, "satra": 17,
    "atharah": 18, "athara": 18, "unnis": 19, "unees": 19, "bees": 20, "bis": 20, "pachchees": 25,
    "pachees": 25, "pachis": 25, "tees": 30, "tis": 30, "paintees": 35, "paintis": 35, "chalis": 40,
    "chaalis": 40, "pachaas": 50, "pachas": 50, "saath": 60, "sattar": 70, "assi": 80, "nabbe": 90,
}
SCALES = {"hundred": 100, "sau": 100, "thousand": 1000, "hazaar": 1000, "hazar": 1000, "hajar": 1000,
          "hajaar": 1000, "k": 1000, "grand": 1000, "lakh": 100000, "lac": 100000}
FRACTIONS = {"dedh": 1.5, "dhai": 2.5, "dhaai": 2.5, "adhai": 2.5}
MODIFIERS = {"saadhe": 0.5, "sade": 0.5, "saade": 0.5, "sava": 0.25, "savaa": 0.25, "paune": -0.25}
# "ek", "do" and "one" are often articles or verbs; they count as numbers only next to a scale word
WEAK_NUMBERS = {"ek", "do", "one", "sat", "tin", "che", "bis", "tis", "saath", "aat", "chah"}

PRICE_CUES = ("under", "below", "within", "max", "maximum", "budget", "upto", "up to", "less than",
              "not more than", "no more than", "at most", "cheaper than", "lower than", "around", "about",
              "for under", "for below", "for less than", "not above", "not over", "under rs", "rs", "inr",
              "rupees", "₹", "ke andar", "se kam", "tak", "range", "price", "spend", "afford", "max of")
SIZE_CUES = {"size", "uk", "waist", "number", "no", "sz", "us"}
CORRECTION_CUES = {"oops", "sorry", "wait", "actually", "rather", "meant", "mean", "change", "make", "no",
                   "nahi", "nahin", "matlab", "instead", "scratch", "correction", "hold", "not", "na",
                   "hmm", "or"}
SOFT_CUES = {"i", "only", "uh", "um", "hmm", "oh", "er", "like", "and", "also"}
NEGATIONS = {"not", "except", "without", "avoid", "but"}


def _norm(word):
    w = word.lower().replace("’", "'")
    w = re.sub(r"^[^\w₹]+", "", w)
    w = re.sub(r"[^\w%]+$", "", w)
    if w.endswith("'s"):
        w = w[:-2]
    return w


class Catalogue:
    """Vocabularies and facet counts learned offline from catalogue.csv. No product IDs are kept."""

    def __init__(self, path=CATALOGUE):
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.brands = {r["brand"].lower(): r["brand"] for r in rows}
        self.sizes = {r["size"] for r in rows if r["size"]}
        self.categories = {r["category"] for r in rows}
        # facet counts: for every subset of (category, colour, brand, size), the prices of matches
        self.facets = defaultdict(list)
        keys = ("category", "colour", "brand", "size")
        for r in rows:
            vals = tuple(r[k] for k in keys)
            for mask in range(16):
                key = tuple(v if mask >> i & 1 else None for i, v in enumerate(vals))
                self.facets[key].append(int(r["price"]))
        self.sized = {r["category"] for r in rows if r["size"]}

    def count(self, f):
        cats = f.get("category")
        cats = cats if isinstance(cats, tuple) else (cats,)
        mp = f.get("max_price")
        total = 0
        for c in cats:
            prices = self.facets.get((c, f.get("colour"), f.get("brand"), f.get("size")), [])
            total += sum(1 for p in prices if mp is None or p <= mp)
        return total


def _build_phrase_index(table):
    idx = []
    for canon, phrases in table.items():
        for p in phrases:
            idx.append((tuple(p.split()), canon))
    idx.sort(key=lambda t: -len(t[0]))
    return idx


CAT_INDEX = _build_phrase_index(CATEGORY_PHRASES)
COL_INDEX = _build_phrase_index(COLOUR_PHRASES)
SIZE_INDEX = [(tuple(k.split()), v) for k, v in sorted(SIZE_PHRASES.items(), key=lambda t: -len(t[0].split()))]

# words that may still grow into a longer phrase with a different meaning
CAT_PREFIXES = {p[:i] for p, _ in CAT_INDEX for i in range(1, len(p))}
COL_PREFIXES = {p[:i] for p, _ in COL_INDEX for i in range(1, len(p))}


class Parser:
    def __init__(self, cat):
        self.cat = cat
        bidx = []
        for low, canon in cat.brands.items():
            bidx.append((tuple(low.split()), canon))
        bidx.sort(key=lambda t: -len(t[0]))
        self.brand_index = bidx
        self.brand_prefixes = {p[:i] for p, _ in bidx for i in range(1, len(p))}

    # ---- numbers ----------------------------------------------------------------------
    @staticmethod
    def _digit_value(w):
        """'1,500' -> 1500, '1.5k' -> 1500, '₹900' -> 900, '2k' -> 2000, '9' -> 9."""
        w = w.replace("₹", "").replace("rs.", "").replace("rs", "").replace("inr", "").replace("/-", "")
        w = w.replace(",", "")
        m = re.fullmatch(r"(\d+(?:\.\d+)?)(k|thousand|l|lakh|hundred)?", w)
        if not m:
            return None
        v = float(m.group(1))
        mult = {"k": 1000, "thousand": 1000, "l": 100000, "lakh": 100000, "hundred": 100}.get(m.group(2), 1)
        return v * mult, bool(m.group(2))

    def _number_spans(self, toks):
        """Find spoken or written numbers. Returns [(start, end, value, has_scale, open_ended)]."""
        spans, i, n = [], 0, len(toks)
        while i < n:
            w = toks[i]
            dv = self._digit_value(w)
            if dv is not None:
                v, scaled = dv
                j = i + 1
                if j < n and toks[j] in SCALES:          # "2 thousand", "15 hundred", "5 k"
                    v *= SCALES[toks[j]]
                    scaled = True
                    j += 1
                spans.append((i, j, v, scaled or v >= 100, j == n))
                i = j
                continue
            a_scale = w == "a" and i + 1 < n and toks[i + 1] in SCALES          # "a thousand"
            if w in UNITS or w in FRACTIONS or w in MODIFIERS or a_scale:
                j, total, cur, frac, mod, scaled = i, 0.0, 0.0, None, 0.0, False
                while j < n:
                    t = toks[j]
                    if t == "a" and cur == 0 and frac is None and j + 1 < n and toks[j + 1] in SCALES:
                        cur = 1.0
                    elif t == "and" and cur and toks[j + 1:j + 3] == ["a", "half"]:   # "three and a half k"
                        cur += 0.5
                        j += 3
                        continue
                    elif t in MODIFIERS and cur == 0 and frac is None:
                        mod = MODIFIERS[t]
                    elif t in FRACTIONS and cur == 0:
                        frac = FRACTIONS[t]
                    elif t in UNITS:
                        if cur and UNITS[t] >= 10 and cur % 100 == 0 and cur >= 100:
                            break
                        if cur and UNITS[t] < 10 and cur % 10 == 0 and cur >= 20:
                            cur += UNITS[t]
                        elif cur and not (cur % 100 == 0):
                            break
                        else:
                            cur += UNITS[t]
                    elif t in SCALES and (cur or frac):
                        base = frac if frac is not None else cur + mod
                        if SCALES[t] >= 1000:
                            total += base * SCALES[t]
                            cur = 0.0
                        else:
                            cur = base * SCALES[t]
                        frac, mod, scaled = None, 0.0, True
                    elif t == "and" and scaled and j + 1 < n and (toks[j + 1] in UNITS):
                        pass
                    else:
                        break
                    j += 1
                value = total + cur
                if frac is not None and not scaled:
                    value = frac
                if j == i or value == 0:
                    i += 1
                    continue
                if j - i == 1 and toks[i] in WEAK_NUMBERS and not scaled:
                    i += 1
                    continue
                spans.append((i, j, value, scaled, j == n))
                i = j
                continue
            i += 1
        return spans

    # ---- main parse --------------------------------------------------------------------
    def parse(self, words):
        """Return (filters, positions, pending) for the words so far.

        filters:   slot -> value, the last valid mention of each slot wins
        positions: slot -> token index where its current value was set
        pending:   slots whose value could still change with the next word
        """
        toks = [_norm(w) for w in words]
        toks = [t for t in toks]
        n = len(toks)
        mentions = []        # (pos, slot, value)
        used = [False] * n
        pending = set()

        def negated(i):
            return i > 0 and toks[i - 1] in NEGATIONS and not (i > 1 and toks[i - 2] in {"no", "nahi"})

        def match_phrases(index, slot, prefixes):
            i = 0
            while i < n:
                hit = None
                for phrase, canon in index:
                    L = len(phrase)
                    if tuple(toks[i:i + L]) == phrase and not any(used[i:i + L]):
                        hit = (L, canon)
                        break
                if hit:
                    L, canon = hit
                    # "price cap 1200", "budget cap": a cap on money, not a product
                    if slot == "category" and canon == "caps" and i > 0 and toks[i - 1] in {"price", "budget", "spending", "spend"}:
                        i += L
                        continue
                    if not negated(i):
                        mentions.append((i + L - 1, slot, canon))
                    for k in range(i, i + L):
                        used[k] = True
                    if i + L == n and tuple(toks[i:i + L]) in prefixes:
                        pending.add(slot)
                    i += L
                else:
                    if i == n - 1 and (toks[i],) in prefixes:
                        pending.add(slot)
                    i += 1

        # brands
        match_phrases(self.brand_index, "brand", self.brand_prefixes)
        # sizes written as phrases ("extra large", "double XL")
        i = 0
        while i < n:
            for phrase, canon in SIZE_INDEX:
                L = len(phrase)
                if tuple(toks[i:i + L]) == phrase:
                    mentions.append((i + L - 1, "size", canon))
                    for k in range(i, i + L):
                        used[k] = True
                    i += L - 1
                    break
            i += 1
        if n and toks[-1] in {"extra", "double", "x", "xx", "2"}:
            pending.add("size")
        # categories and colours
        match_phrases(CAT_INDEX, "category", CAT_PREFIXES)
        match_phrases(COL_INDEX, "colour", COL_PREFIXES)

        # numbers: prices and numeric sizes
        for (s, e, v, scaled, open_end) in self._number_spans(toks):
            if any(used[s:e]):
                continue
            prev = toks[s - 1] if s > 0 else ""
            prev2 = " ".join(toks[max(0, s - 3):s])
            nxt = toks[e] if e < n else ""
            size_ctx = prev in SIZE_CUES or nxt in {"uk", "waist", "number", "size", "us"} or \
                (prev in {"in", "of"} and s > 1 and toks[s - 2] in {"size", "uk"})
            price_ctx = any(prev2.endswith(c) for c in PRICE_CUES) or nxt in {"rupees", "rs", "tak", "se",
                                                                              "ke", "only", "inr", "budget"}
            iv = int(round(v))
            if (scaled or v >= 100 or price_ctx) and not (size_ctx and v < 100):
                if iv >= 50:
                    mentions.append((e - 1, "max_price", iv))
                    if open_end:
                        pending.add("max_price")
            elif str(iv) in self.cat.sizes or size_ctx:
                if str(iv) in self.cat.sizes:
                    mentions.append((e - 1, "size", str(iv)))
                    if open_end:
                        pending.add("size")
            for k in range(s, e):
                used[k] = True

        # letter sizes: XS, S, M, L, XL, XXL, small, medium, large ...
        for i, t in enumerate(toks):
            if used[i]:
                continue
            if t in LETTER_SIZES:
                canon = LETTER_SIZES[t]
                # single letters are only sizes next to a size cue or a garment, never "i", "a" etc.
                if t in {"s", "m", "l"}:
                    near = {toks[k] for k in range(max(0, i - 2), min(n, i + 3)) if k != i}
                    garment_ctx = bool(near & {"size", "sizes"}) or (i + 1 < n and toks[i + 1] == "size") \
                        or (i > 0 and toks[i - 1] == "size")
                    if not garment_ctx and not (i > 0 and words[i].strip(",.!?")[:1].isupper()):
                        continue
                if not negated(i):
                    mentions.append((i, "size", canon))
                    used[i] = True
            elif t == "size" and i == n - 1:
                pending.add("size")

        if n and toks[-1] in {"size", "uk", "waist", "under", "below", "budget", "max", "within", "than",
                              "to", "upto", "rs", "₹"}:
            pending.add("size" if toks[-1] in {"size", "uk", "waist"} else "max_price")

        filters, positions = {}, {}
        for pos, slot, val in sorted(mentions, key=lambda m: m[0]):
            filters[slot] = val
            positions[slot] = pos
        # a size on an unsized category is noise ("size" of a cap)
        cats = filters.get("category")
        if cats and not any(c in self.cat.sized for c in (cats if isinstance(cats, tuple) else (cats,))):
            filters.pop("size", None)
        return filters, positions, pending


class Agent:
    """Facet-gated early-commit shopping agent.

    Tunable: AGENT_MAX_SEARCHES (env) caps searches per request (stretch goal: a limit on wasted
    searches). The default policy already uses about 1.02 searches per request.
    """

    # risk policy, tuned on a held-out split of dev.jsonl
    QUIET_WORDS = 0          # words after the deciding word with no correction cue before committing
    BOUNDARY_WAIT = True     # hold one word at clause boundaries, where corrections start
    WAIT_PENDING = True      # never commit while a slot is mid-phrase (a number still being spoken)

    def __init__(self, tools):
        import os
        self.tools = tools
        self.max_searches = int(os.environ.get("AGENT_MAX_SEARCHES", "3"))
        self.cat = Catalogue()
        self.parser = Parser(self.cat)

    def start(self, request_id):
        self.words = []
        self.committed = None        # product dict
        self.stable_since = None
        self.last_filters = None
        self.searched = {}           # frozen filters -> result list

    # ---- helpers -------------------------------------------------------------------------
    def _search(self, filters, k=2):
        """One counted search. A set of candidate categories is searched once without the
        category filter, and the results are narrowed to the set."""
        key = tuple(sorted((a, str(b)) for a, b in filters.items()))
        if key not in self.searched and len(self.searched) >= self.max_searches:
            return []
        if key not in self.searched:
            f = dict(filters)
            cats = f.get("category")
            if isinstance(cats, tuple):
                f.pop("category")
                hits = [h for h in self.tools.search("", f, k=200) if h["category"] in cats]
                self.searched[key] = hits[:k]
            else:
                self.searched[key] = self.tools.search("", f, k=k)
        return self.searched[key]

    @staticmethod
    def _matches(p, f):
        for k in ("category", "colour", "brand", "size"):
            want = f.get(k)
            if want is None:
                continue
            options = want if isinstance(want, tuple) else (want,)
            if str(p.get(k, "")).lower() not in {str(o).lower() for o in options}:
                return False
        if f.get("max_price") is not None and int(p["price"]) > f["max_price"]:
            return False
        return True

    def _recent_correction_cue(self, lookback):
        recent = [_norm(w) for w in self.words[-lookback:]]
        return any(w in CORRECTION_CUES for w in recent)

    # ---- protocol ------------------------------------------------------------------------
    def observe(self, word):
        self.words.append(word)
        filters, positions, pending = self.parser.parse(self.words)
        stable = {k: v for k, v in filters.items() if k not in pending}
        report = {"filters": dict(filters), "confidence": 0.0}
        t = len(self.words)
        # a slot that changed value (not merely added) restarts the quiet period
        if self.last_filters is not None and any(
                k in self.last_filters and self.last_filters[k] != v for k, v in stable.items()):
            self.stable_since = None
        self.last_filters = dict(stable)
        if self.committed is not None:
            report["confidence"] = 1.0 if self._matches(self.committed, filters) else 0.0
            return report

        count = self.cat.count(stable) if stable else len(self.cat.facets[(None,) * 4])
        if count != 1:
            self.stable_since = None
            return report
        if self.stable_since is None:
            self.stable_since = t
        if self.WAIT_PENDING and pending:
            return report
        # an open correction: a cue word after the latest slot mention, not yet resolved
        last_mention = max(positions.values()) if positions else -1
        open_cue = any(_norm(w) in CORRECTION_CUES for w in self.words[last_mention + 1:])
        quiet = t - self.stable_since
        report["confidence"] = 0.5 + 0.5 * min(1.0, quiet / max(1, self.QUIET_WORDS))
        if open_cue or quiet < self.QUIET_WORDS:
            return report
        # Corrections almost always open right after a clause boundary ("size M. sorry, I meant XL")
        # or with a hedge word ("I mean", "only"). At those points, listen to one more word first.
        cur = self.words[-1]
        if self.BOUNDARY_WAIT and (re.search(r"[,.;!?]$", cur) or _norm(cur) in SOFT_CUES):
            return report
        hits = self._search(stable)
        if len(hits) == 1:
            self.committed = hits[0]
            report["commit"] = hits[0]["product_id"]
            report["confidence"] = 1.0
        return report

    def finish(self):
        filters, _, _ = self.parser.parse(self.words)
        if self.committed is not None and self._matches(self.committed, filters):
            return self.committed["product_id"]
        # relax filters from least to most reliable until something matches
        for drop in ((), ("max_price",), ("size",), ("brand",), ("colour",), ("max_price", "size")):
            f = {k: v for k, v in filters.items() if k not in drop}
            if not f:
                break
            hits = self._search(f, k=1)
            if hits:
                return hits[0]["product_id"]
        hits = self.tools.search(" ".join(self.words), {}, k=1)
        return hits[0]["product_id"] if hits else None
