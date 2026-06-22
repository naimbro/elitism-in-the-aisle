#!/usr/bin/env python3
"""
BCN reseñas → structured biographical fields, for criterion validation of the
surname-based elite measure (paper_1925). Extracts NON-surname class markers so
the validation stays independent of the construction (and of the surname itself).

Two fixes discovered in the 20-profile exploration are baked in:
  (1) gzip: Wayback `id_` returns raw stored bytes; some captures are gzip-encoded
      and must be decompressed (profile 09 came back as binary garbage otherwise).
  (2) TOC slicing: modern pages list "Parlamentario en el hemiciclo" in the table
      of contents BEFORE the real bio sections; slice at the LAST occurrence.

Scale-up: needs ANTHROPIC_API_KEY. ~3.2-4.7k pages → use the Batch API for cost.
Run a single page:  python bcn_extractor.py --url <wayback_url> --ts <timestamp>
"""
import os, re, gzip, json, io, urllib.request, urllib.parse, argparse

UA = {"User-Agent": "Mozilla/5.0 (research; biographic validation; naim.bro@gmail.com)"}

def fetch_raw(url, ts):
    req = urllib.request.Request(f"http://web.archive.org/web/{ts}id_/{url}", headers=UA)
    raw = urllib.request.urlopen(req, timeout=60).read()
    if raw[:2] == b"\x1f\x8b":                      # FIX 1: gzip magic
        raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    return raw.decode("utf-8", "replace")

def visible_text(h):
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;", " ", t); t = re.sub(r"&[a-z]+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def bio_core(t):
    a = re.search(r"(Antecedentes Personales|Trayectoria Parlamentaria)", t)
    s = a.start() if a else 0
    # FIX 2: cut at the LAST hemiciclo mention (TOC lists it before the body)
    ends = [m.start() for m in re.finditer(r"Parlamentario en el [Hh]emiciclo", t)]
    boiler = re.search(r"(Buscando contenido multimedia|Colabore con fotograf|PORTAL BCN)", t)
    end = max(ends) if ends else (boiler.start() if boiler else min(len(t), s + 6000))
    return t[s:end][:6000]

SCHEMA = {
  "type": "object",
  "properties": {
    "birth_year": {"type": ["integer", "null"]},
    "birth_place": {"type": ["string", "null"]},
    "death_year": {"type": ["integer", "null"]},
    "father_name": {"type": ["string", "null"]},
    "father_surname_paternal": {"type": ["string", "null"]},
    "father_surname_maternal": {"type": ["string", "null"]},
    "mother_name": {"type": ["string", "null"]},
    "mother_surname_paternal": {"type": ["string", "null"]},
    "nobiliary_particle": {"type": "boolean", "description": "any 'de X' nobiliary form in self or parents"},
    "spouse_surnames": {"type": "array", "items": {"type": "string"}},
    "profession": {"type": "array", "items": {"type": "string"}},
    "occupation_category": {"type": "string", "enum": ["law","medicine","military","clergy","business","mining","agriculture","engineering","education","journalism","public_admin","other","unknown"]},
    "elite_secondary_school": {"type": "boolean", "description": "San Ignacio, Sagrados Corazones, The Grange, Verbo Divino, Craighouse, Saint George, Convictorio Carolino, etc."},
    "secondary_school": {"type": ["string", "null"]},
    "university": {"type": ["string", "null"]},
    "university_degree": {"type": ["string", "null"]},
    "postgrad_abroad": {"type": "boolean"},
    "elite_club": {"type": "boolean", "description": "Club de la Unión, Club Hípico, Country Club, etc."},
    "landholding": {"type": "boolean", "description": "owns hacienda/fundo or 'actividades agrícolas'"},
    "richness": {"type": "string", "enum": ["rich","medium","sparse"]},
    "independent_elite_score": {"type": "integer", "description": "0-5: count of NON-surname elite markers present (elite school, elite club, law/medicine degree, postgrad abroad, landholding, nobiliary parents). DO NOT use the person's own surname."},
    "notes": {"type": "string"}
  },
  "required": ["richness","independent_elite_score","occupation_category","nobiliary_particle","elite_secondary_school","elite_club","landholding","postgrad_abroad","profession","spouse_surnames"]
}

PROMPT = (
 "You are extracting structured biographical data from a Chilean parliamentary reseña "
 "(Biblioteca del Congreso Nacional) to validate a surname-based elite measure. "
 "Extract ONLY what the text states; use null/false when absent. CRITICAL: judge "
 "`independent_elite_score` from class markers OTHER than the person's own surname "
 "(parents' status & nobiliary 'de', elite school, elite social club, prestige degree "
 "in law/medicine, study abroad, landholding) — never from the surname itself, to keep "
 "the validation independent. Return via the tool.\n\nRESEÑA TEXT:\n")

def extract(text):
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        tools=[{"name": "record", "description": "Record extracted fields", "input_schema": SCHEMA}],
        tool_choice={"type": "tool", "name": "record"},
        messages=[{"role": "user", "content": PROMPT + text[:6000]}],
    )
    for b in msg.content:
        if b.type == "tool_use":
            return b.input
    return None

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True); ap.add_argument("--ts", required=True)
    a = ap.parse_args()
    core = bio_core(visible_text(fetch_raw(a.url, a.ts)))
    print(json.dumps(extract(core), ensure_ascii=False, indent=2))
