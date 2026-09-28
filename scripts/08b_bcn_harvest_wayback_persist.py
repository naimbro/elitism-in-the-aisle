"""Re-run of 08_bcn_harvest_wayback.py with PERSISTENT paths.

The 2026-06-20 run wrote to /tmp and was lost on reboot. This version writes to
data/raw/bcn_wayback/ inside the repo tree. CDX index regenerated 2026-07-10
(cdx_historiapolitica.txt + cdx_biografias.txt -> cdx.txt, 4,896 status-200 pages).
"""
import urllib.parse, urllib.request, unicodedata, re, time, json, os, gzip, io
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

BASE = "/mnt/c/Users/naim.bro.k/documents/datos/papers/paper_1925"
OUT = f"{BASE}/data/raw/bcn_wayback"; os.makedirs(OUT, exist_ok=True)
CDX = f"{BASE}/data/raw/cdx.txt"
CONG = f"{BASE}/replication_repo/data/processed/cong_df.csv"
UA = {"User-Agent": "Mozilla/5.0 (research; biographic validation; naim.bro@gmail.com)"}

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii","ignore").decode()
    return re.sub(r"\s+"," ", s).upper().strip()

# archived 200 pages: normalized-name -> (url, timestamp)
arch = {}
for l in open(CDX):
    r = l.split()
    if len(r) >= 3 and r[2] == "200":
        slug = r[0].split("/wiki/")[-1]
        if not slug or "$" in slug or "%E0" in slug or slug == "redirect": continue
        nm = urllib.parse.unquote(slug).replace("_"," ")
        if re.search(r"[A-Za-z]", nm): arch.setdefault(norm(nm), (r[0], r[1]))

df = pd.read_csv(CONG)
df["Start"] = pd.to_numeric(df["Start"], errors="coerce")
df["nm"] = df["Name"].map(norm)
agg = df.groupby("nm").agg(Start=("Start","min"), Pat=("Pat","first"),
                           Mat=("Mat","first"), Name=("Name","first"),
                           Camara=("Camara","first"), Party=("Partido","first")).reset_index()
matched = agg[agg["nm"].isin(arch)].copy()
print(f"matched legislators with archived reseña: {len(matched)}", flush=True)

def visible(h):
    t = re.sub(r"(?is)<(script|style).*?</\1>"," ", h); t = re.sub(r"(?s)<[^>]+>"," ", t)
    t = re.sub(r"&nbsp;"," ", t); t = re.sub(r"&[a-z]+;"," ", t)
    return re.sub(r"\s+"," ", t).strip()

def core(t):
    a = re.search(r"(Antecedentes Personales|Trayectoria Parlamentaria)", t)
    s = a.start() if a else 0
    ends = [m.start() for m in re.finditer(r"Parlamentario en el [Hh]emiciclo", t)]
    b = re.search(r"(Buscando contenido multimedia|Colabore con fotograf|PORTAL BCN)", t)
    end = max(ends) if ends else (b.start() if b else min(len(t), s+6000))
    return t[s:end][:6000]

def fetch(row):
    nm = row.nm; out = f"{OUT}/{nm.replace(' ','_')[:80]}.txt"
    if os.path.exists(out): return ("skip", nm)
    url, ts = arch[nm]
    body = None; last = "?"
    for attempt in range(4):
        try:
            req = urllib.request.Request(f"http://web.archive.org/web/{ts}id_/{url}", headers=UA)
            raw = urllib.request.urlopen(req, timeout=90).read()
            if raw[:2] == b"\x1f\x8b": raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            body = core(visible(raw.decode("utf-8","replace")))
            break
        except Exception as ex:
            last = str(ex)[:50]; time.sleep(2 * (attempt + 1))
    if body is None:
        return ("err", f"{nm}: {last}")
    hdr = (f"NAME: {row.Name}\nSTART: {int(row.Start) if pd.notna(row.Start) else ''}\n"
           f"CAMARA: {row.Camara}\nPAT: {row.Pat}\nMAT: {row.Mat}\nPARTY: {row.Party}\n---\n")
    open(out,"w").write(hdr + body + "\n")
    time.sleep(0.3)
    return ("ok", nm)

rows = list(matched.itertuples(index=False))
done = err = skip = 0
with ThreadPoolExecutor(max_workers=2) as ex:
    futs = [ex.submit(fetch, r) for r in rows]
    for i, f in enumerate(as_completed(futs), 1):
        status, msg = f.result()
        if status == "ok": done += 1
        elif status == "skip": skip += 1
        else: err += 1
        if i % 200 == 0:
            print(f"  {i}/{len(rows)}  ok={done} skip={skip} err={err}", flush=True)

print(f"DONE. ok={done} skip={skip} err={err}  files in {OUT}", flush=True)
json.dump({"matched": len(matched), "ok": done, "skip": skip, "err": err},
          open(f"{OUT}/_manifest.json","w"))
