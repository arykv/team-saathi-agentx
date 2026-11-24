"""Turn proposed requests (JSON lines with text + filters) into an evaluate.py dataset.
Keeps a request only if its filters match exactly one catalogue product and the text names its brand."""
import csv, json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(HERE / "catalogue.csv")))
def match(p, f):
    for k in ("category", "colour", "brand", "size"):
        if f.get(k) not in (None, "") and p[k].lower() != str(f[k]).lower():
            return False
    return not (f.get("max_price") and int(p["price"]) > int(f["max_price"]))
out, kept, dropped = [], 0, 0
for src in sys.argv[2:]:
    for line in Path(src).read_text().splitlines():
        line = line.strip().strip(",")
        if not line.startswith("{"):
            continue
        try:
            x = json.loads(line)
        except Exception:
            dropped += 1; continue
        f = {k: (x["filters"].get(k) or None) for k in ("category", "colour", "size", "brand", "max_price")}
        if f["size"] is not None: f["size"] = str(f["size"])
        m = [p for p in rows if match(p, f)]
        brand_ok = f["brand"] is None or f["brand"].lower() in x["text"].lower()
        if len(m) != 1 or not brand_ok:
            dropped += 1; continue
        words = x["text"].split()
        out.append({"id": f"syn-{len(out)+1:04d}", "text": x["text"], "words": words, "filters": f,
                    "target": m[0]["product_id"], "earliest": len(words), "tags": x.get("tags", [])})
        kept += 1
Path(sys.argv[1]).write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out))
print(f"kept {kept}, dropped {dropped} -> {sys.argv[1]}")
