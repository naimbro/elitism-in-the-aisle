import os, re, glob, sys, json, time
from pathlib import Path
# Repo root = parent of this scripts/ directory; raw/auxiliary sources live OUTSIDE the repo.
REPO = Path(__file__).resolve().parents[1]
# RAW_DATA_ROOT: paper project dir (default), env-overridable -- same anchor as the other
# scripts. It also holds bcn_extractor.py (the prompt/schema module) and the shared .env.
RAW_DATA_ROOT = Path(os.environ.get("RAW_DATA_ROOT", REPO.parent))
# .env holding ANTHROPIC_API_KEY: skip if the key is already in the environment or the
# file is absent. Override the location with ANTHROPIC_ENV_FILE.
_env_file = Path(os.environ.get(
    "ANTHROPIC_ENV_FILE", RAW_DATA_ROOT.parent / "2026_faction_detection" / ".env"))
if "ANTHROPIC_API_KEY" not in os.environ and _env_file.exists():
    for l in open(_env_file):
        if l.startswith("ANTHROPIC_API_KEY="):
            os.environ["ANTHROPIC_API_KEY"] = l.split("=",1)[1].strip()
# bcn_extractor.py (PROMPT + SCHEMA) lives in the paper project dir (RAW_DATA_ROOT),
# alongside the elite workbook -- not in the public repo. Override via BCN_EXTRACTOR_DIR.
sys.path.insert(0, os.environ.get("BCN_EXTRACTOR_DIR", str(RAW_DATA_ROOT)))
import bcn_extractor as bx
import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
client = anthropic.Anthropic()

files = sorted(glob.glob("/tmp/harvest_all/*.txt"))
def meta(path):
    h = open(path).read()
    head, _, body = h.partition("\n---\n")
    d = dict(re.findall(r"^([A-Z]+): ?(.*)$", head, re.M))
    return d, body.strip()

idmap = {}
reqs = []
for i, f in enumerate(files):
    d, body = meta(f)
    cid = f"p{i:05d}"
    idmap[cid] = {"file": f, "name": d.get("NAME",""), "start": d.get("START",""),
                  "camara": d.get("CAMARA",""), "pat": d.get("PAT",""), "mat": d.get("MAT","")}
    reqs.append(Request(custom_id=cid, params=MessageCreateParamsNonStreaming(
        model="claude-sonnet-4-6", max_tokens=700,
        system=[{"type":"text","text":bx.PROMPT,"cache_control":{"type":"ephemeral"}}],
        tools=[{"name":"record","description":"Record extracted biographical fields","input_schema":bx.SCHEMA}],
        tool_choice={"type":"tool","name":"record"},
        messages=[{"role":"user","content": body or "(no content)"}],
    )))
json.dump(idmap, open("/tmp/extract_idmap.json","w"))
print(f"submitting batch: {len(reqs)} requests", flush=True)

batch = client.messages.batches.create(requests=reqs)
print(f"batch id: {batch.id}", flush=True)
open("/tmp/extract_batch_id.txt","w").write(batch.id)

while True:
    b = client.messages.batches.retrieve(batch.id)
    if b.processing_status == "ended": break
    c = b.request_counts
    print(f"  status={b.processing_status} done={c.succeeded} err={c.errored} proc={c.processing}", flush=True)
    time.sleep(30)

print("batch ended, collecting...", flush=True)
recs = []; tin=tout=tcw=tcr=0; ok=err=0
for res in client.messages.batches.results(batch.id):
    info = idmap.get(res.custom_id, {})
    if res.result.type == "succeeded":
        msg = res.result.message
        u = msg.usage
        tin += u.input_tokens; tout += u.output_tokens
        tcw += getattr(u,"cache_creation_input_tokens",0) or 0
        tcr += getattr(u,"cache_read_input_tokens",0) or 0
        fields = next((b.input for b in msg.content if b.type=="tool_use"), None)
        if fields is not None: ok += 1
        recs.append({**info, "fields": fields})
    else:
        err += 1
        recs.append({**info, "fields": None, "error": str(res.result.type)})

json.dump(recs, open("/tmp/extract_sonnet.json","w"), ensure_ascii=False)
# actual cost (Sonnet batch: $1.5/M in, $7.5/M out; cache read 0.1x, write 1.25x of base*0.5)
cost = (tin/1e6)*1.5 + (tout/1e6)*7.5 + (tcr/1e6)*0.15 + (tcw/1e6)*1.875
print(f"\nDONE  ok={ok} err={err}  tokens in={tin} out={tout} cache_w={tcw} cache_r={tcr}")
print(f"ACTUAL COST ≈ ${cost:.2f}  -> /tmp/extract_sonnet.json", flush=True)
