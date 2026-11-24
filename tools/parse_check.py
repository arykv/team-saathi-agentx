"""Parser-level check: compare parsed filters with gold, for any text (no catalogue match needed)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import Catalogue, Parser
P = Parser(Catalogue())
bad = 0
lines = [json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines() if l.strip().startswith("{")]
for x in lines:
    got, _, _ = P.parse(x["text"].split())
    gold = {k: (str(v) if k == "size" else tuple(v) if isinstance(v, list) else v) for k, v in x["filters"].items() if v not in (None, "")}
    if got != gold:
        bad += 1
        print("MISS", x["text"], "\n   got ", got, "\n   gold", gold)
print(f"{len(lines) - bad}/{len(lines)} parsed exactly")
