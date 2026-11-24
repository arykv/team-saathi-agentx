"""Ask local Qwen for shopping requests with fresh wording, to stress-test the parser.
Output is a proposal: tools/validate_synth.py checks every label against catalogue.csv."""
import csv, json, random, sys, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(HERE / "catalogue.csv")))
random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
# pick real products so every request has exactly one answer
picks = random.sample(rows, 40)
specs = []
for p in picks:
    f = {"category": p["category"], "colour": p["colour"], "brand": p["brand"], "size": p["size"] or None}
    price = int(p["price"])
    f["max_price"] = random.choice([None, (price // 500 + 1) * 500, (price // 100 + 1) * 100])
    specs.append(f)
examples = [json.loads(l)["text"] for l in open(HERE / "dev.jsonl")][:12]
prompt = f"""You write realistic shopping requests that Indian shoppers type or say to a store assistant.
For EACH spec below write ONE request that asks for exactly those filters (category, colour, brand, size, max_price;
null means do not mention it). Mix styles across the 40:
- about 40% plain English but with UNUSUAL wording: different verbs and openers, synonyms for the product type
  (e.g. trainers, lowers, chappals, frock, earphones, purse, school bag, kicks, sweatpants, timepiece),
  sizes said differently (e.g. "a medium", "XL fit", "UK nine", "waist thirty two"), prices said differently
  (e.g. "budget is around 2k max", "nothing over 1500", "keep it under two grand", "₹1.2k tops")
- about 20% Hindi-English code-mixed (e.g. "mujhe", "chahiye", "kaala", "neela", "safed", "dedh hazaar tak")
- about 20% with a CORRECTION where a wrong value is said first then corrected ("navy, no sorry, black")
- about 20% with a LATE constraint added after the request sounds finished ("... oh and make it size M")
Never mention a filter that is null. Brands must be spelled exactly as given. Colours must be clearly the given colour.
Style examples (do not copy their wording): {json.dumps(examples)}
SPECS: {json.dumps(specs)}
Return ONLY JSON lines, one per spec, in order: {{"text": "...", "filters": <the spec exactly>, "tags": [...]}}
tags from: "correction", "late_constraint", "code_mixed" (empty list for plain)."""
body = json.dumps({"model": "qwen3.8:27b-mlx", "stream": False, "think": False,
                   "messages": [{"role": "user", "content": prompt}],
                   "options": {"temperature": 0.9, "num_ctx": 16384}}).encode()
req = urllib.request.Request("http://127.0.0.1:11434/api/chat", body, {"Content-Type": "application/json"})
out = json.loads(urllib.request.urlopen(req, timeout=1500).read())["message"]["content"]
Path(sys.argv[1]).write_text(out)
print("wrote", sys.argv[1], len(out.splitlines()), "lines")
