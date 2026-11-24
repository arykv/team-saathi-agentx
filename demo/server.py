"""Live demo for the jury: type or speak a request and watch the agent decide word by word.
    python demo/server.py     ->  http://localhost:8790
POST /trace {"text": "..."} replays the real Agent over the words and returns every step."""
import http.server, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent import Agent            # noqa: E402
from evaluate import Tools         # noqa: E402

AGENT = Agent(Tools())


def trace(text):
    words = text.split()
    AGENT.tools.searches = 0
    AGENT.start("demo")
    steps = []
    for i, w in enumerate(words, 1):
        t0 = time.perf_counter()
        out = AGENT.observe(w) or {}
        ms = (time.perf_counter() - t0) * 1000
        f, _, pending = AGENT.parser.parse(AGENT.words)
        stable = {k: v for k, v in f.items() if k not in pending}
        steps.append({"i": i, "word": w, "filters": {k: (list(v) if isinstance(v, tuple) else v) for k, v in f.items()},
                      "pending": sorted(pending), "candidates": AGENT.cat.count(stable) if stable else None,
                      "commit": out.get("commit"), "ms": round(ms, 3), "searches": AGENT.tools.searches})
    final = AGENT.finish()
    prod = next((r for r in AGENT.searched.values() for r in r if r["product_id"] == final), None)
    if prod is None and final:
        from search import load_catalogue
        prod = next(p for p in load_catalogue() if p["product_id"] == final)
    return {"steps": steps, "final": final, "product": prod, "searches": AGENT.tools.searches}


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(Path(__file__).parent), **k)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or "{}")
        res = json.dumps(trace(body.get("text", "")), ensure_ascii=False).encode()
        self.send_response(200); self.send_header("content-type", "application/json"); self.end_headers()
        self.wfile.write(res)

    def log_message(self, *a):
        pass


port = int(os.environ.get("PORT", 8790))
print(f"AgentX demo on http://localhost:{port}")
http.server.ThreadingHTTPServer(("", port), H).serve_forever()
