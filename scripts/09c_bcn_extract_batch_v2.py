"""BCN reseñas -> structured biographical fields. v2 re-run (2026-07-10).

Changes vs 09_bcn_extract_batch.py (the lost 2026-06-20 run):
  - PERSISTENT paths (the v1 outputs lived in /tmp and were wiped).
  - Input = data/raw/bcn_wayback/*.txt (3,417 files, re-harvested 2026-07-10).
  - Prompt caching FIXED: v1's prefix was 1,265 tok < the min cacheable prefix, so
    cache_read=0 and cost doubled. The system prompt below is a full extraction
    manual (~1.5k tok); tools+system together clear the ~2,048-token minimum.
  - Class-coding lesson applied: Instituto Nacional & public liceos are explicitly
    NOT elite schools (v1 miscoded 311/625). Factual fields are primary; judgment
    fields kept for continuity but 10_bcn_quality_correct.py still applies.
  - New factual fields for the Juridical Shield test: judicial_office,
    ministerial_office.
  - Model: claude-sonnet-5 (successor of v1's sonnet; intro batch pricing).

Usage:
  python 09c_bcn_extract_batch_v2.py --smoke 3     # synchronous sanity check
  python 09c_bcn_extract_batch_v2.py               # submit full batch + poll
"""
import os, re, glob, json, time, argparse
from pathlib import Path

BASE = Path("/mnt/c/Users/naim.bro.k/documents/datos/papers/paper_1925")
IN_DIR = BASE / "data/raw/bcn_wayback"
OUT_DIR = BASE / "data/processed"; OUT_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = Path("/mnt/c/Users/naim.bro.k/documents/datos/papers/paper_brahmin/.env")

if "ANTHROPIC_API_KEY" not in os.environ and ENV_FILE.exists():
    for l in open(ENV_FILE):
        if l.startswith("ANTHROPIC_API_KEY="):
            os.environ["ANTHROPIC_API_KEY"] = l.split("=", 1)[1].strip()

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

MODEL = "claude-sonnet-5"

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
    "nobiliary_particle": {"type": "boolean"},
    "spouse_surnames": {"type": "array", "items": {"type": "string"}},
    "profession": {"type": "array", "items": {"type": "string"}},
    "occupation_category": {"type": "string", "enum": ["law","medicine","military","clergy","business","mining","agriculture","engineering","education","journalism","public_admin","other","unknown"]},
    "judicial_office": {"type": "boolean", "description": "held a JUDICIAL post: juez, ministro de corte, fiscal judicial, relator"},
    "ministerial_office": {"type": "boolean", "description": "served as Ministro de Estado (cabinet minister)"},
    "secondary_school": {"type": ["string", "null"]},
    "elite_secondary_school": {"type": "boolean"},
    "university": {"type": ["string", "null"]},
    "university_degree": {"type": ["string", "null"]},
    "postgrad_abroad": {"type": "boolean"},
    "elite_club": {"type": "boolean"},
    "landholding": {"type": "boolean"},
    "richness": {"type": "string", "enum": ["rich","medium","sparse"]},
    "independent_elite_score": {"type": "integer"},
    "notes": {"type": "string"}
  },
  "required": ["richness","independent_elite_score","occupation_category","nobiliary_particle",
               "elite_secondary_school","elite_club","landholding","postgrad_abroad",
               "judicial_office","ministerial_office","profession","spouse_surnames"]
}

SYSTEM = """You are extracting structured biographical data from Chilean parliamentary reseñas (biographical sketches published by the Biblioteca del Congreso Nacional, BCN). Each user message contains the visible text of one reseña, sometimes preceded by a metadata header (NAME/START/CAMARA/PAT/MAT/PARTY) added by our harvester. The reseñas cover legislators from 1811 to the present, so the Spanish ranges from 19th-century orthography ("i" for "y", "jeneral") to modern text; OCR-free but occasionally garbled by web-archiving. Extract ONLY what the text states or directly implies; use null for absent scalar fields, false for absent boolean markers, and empty arrays when nothing applies. Never guess from the person's surname or fame. Return the record via the tool call, nothing else.

FIELD-BY-FIELD MANUAL

birth_year / death_year: four-digit years only. "Nació en Chillán en 1880" -> 1880. If only an age at death and a death date are given, do not compute the birth year — leave it null. birth_place: the town/city as written ("Chillán", "Santiago", "Valparaíso"); strip province qualifiers only if clearly redundant.

father_name / mother_name: full names as written from phrases like "Hijo de Juan N. Concha Melo y de Macedonia Aramburu". father_surname_paternal is the father's FIRST surname (Concha in the example); father_surname_maternal his second (Melo). mother_surname_paternal is the mother's first surname (Aramburu). Chilean usage: a person's first surname comes from the father, the second from the mother. Married women often appear as "de [husband's surname]" — "Mercedes Valdés de Errázuriz" has paternal surname Valdés, not Errázuriz. Ignore "viuda de", "v. de".

nobiliary_particle: true only for genuine compound nobiliary/colonial forms in the person's or parents' surnames ("Fernández de Castro", "Ruiz de Gamboa", "García de la Huerta"). The bare preposition in place names or in "de la Cruz"-type devotional surnames of humble families does NOT count if context suggests otherwise; when in doubt on a compound surname, true.

spouse_surnames: paternal surnames of all spouses mentioned ("Casado con Julia Krefft R." -> ["Krefft"]). Empty array if unmarried or unstated.

profession: every profession/occupation stated, in Spanish, lowercase ("abogado", "médico", "agricultor", "profesor", "periodista", "ingeniero", "militar", "sacerdote", "comerciante", "minero"). "Juró como abogado" or a law degree with professional practice -> include "abogado". occupation_category: the PRIMARY lifetime occupation, mapped to the enum. A lawyer who was mainly a landowner-farmer is "agriculture" with "abogado" still listed in profession; a career military officer is "military". If the reseña gives only the parliamentary career, use "unknown".

judicial_office: true ONLY for formal posts in the judiciary: juez (de letras, del crimen, etc.), ministro de Corte (Suprema or de Apelaciones), fiscal de Corte / fiscal judicial, relator, secretario de juzgado promoted to judgeship. Being an abogado, notary (notario), or conservador de bienes raíces does NOT count. ministerial_office: true if the person served as Ministro de Estado / cabinet minister (Hacienda, Interior, Justicia, Guerra, Relaciones Exteriores, etc.); intendente, diplomat, or subsecretario do NOT count.

secondary_school: the school named for secondary studies ("Liceo de Concepción", "Instituto Nacional", "Colegio San Ignacio"). elite_secondary_school: true ONLY for private elite schools: San Ignacio, Sagrados Corazones (Padres Franceses), The Grange, Verbo Divino, Craighouse, Saint George, Colegio Alemán in its fee-paying form, Convictorio Carolino, seminaries attended by the aristocracy when the text signals status. CRITICAL: the Instituto Nacional and the public liceos (Liceo de Aplicación, Liceo de Concepción, Liceo de Talca, etc.) are PUBLIC meritocratic schools and are NEVER elite_secondary_school=true, no matter how prestigious — this was the main coding error in a previous run; do not repeat it.

university: institution of higher study ("Universidad de Chile", "Universidad Católica", "Universidad de San Felipe"). university_degree: the degree/title ("Licenciado en Leyes", "Médico Cirujano", "Ingeniero Civil"). postgrad_abroad: true if the person studied abroad after their Chilean degree (Europe or USA; "perfeccionó estudios en París").

elite_club: true if member of Club de la Unión, Club Hípico, Club de Septiembre, Club de Viña del Mar, Country Club, Jockey Club, or equivalent aristocratic social clubs. Political party clubs, workers' societies (sociedades de socorros mutuos), masonic lodges, and the Club de la República do NOT count. Note: masonic membership is common in these bios ("Masón") — it is NOT an elite club for this field.

landholding: true if the person owned or managed rural estates: "hacendado", "dueño del fundo X", "agricultor" when clearly an estate owner, "se dedicó a las labores agrícolas en su fundo". Urban real estate does not count; being the SON of a hacendado does not count unless the person inherited/managed it.

richness: how much biographical detail the reseña itself contains — "rich" (family, education, career, properties, several paragraphs), "medium" (basic career plus some personal data), "sparse" (little more than the parliamentary record).

independent_elite_score: integer 0-5 counting how many of these NON-surname elite markers are present: (1) elite private secondary school, (2) elite social club, (3) prestige degree in law or medicine, (4) postgraduate study abroad, (5) landholding, (6) nobiliary/high-status parents (nobiliary particle or parents described with titles/estates). Cap at 5. NEVER infer status from the person's own surname or from relatives in politics — the score must stay independent of surname-based measures.

notes: 1-3 sentences summarizing anything analytically useful that the fields cannot hold: expropriation or land-reform mentions, family ties to other politicians, business directorships, exile, party switches.

GENERAL RULES: metadata in the harvester header (party, chamber, term start) is context, not biography — extract from the body text. Text after "Bio-bibliografía" or "Fuentes bibliográficas" lists publications and sources; use it only for profession hints (a "Memoria de Prueba" thesis implies a university degree). Wiki navigation junk ("Vistas Herramientas personales Entrar...") is noise — ignore it. If two conflicting statements appear, prefer the more specific one. Always produce the tool call even for very sparse bios; a record of nulls and falses with richness="sparse" is a valid result."""

def meta(path):
    h = open(path, encoding="utf-8").read()
    head, _, body = h.partition("\n---\n")
    d = dict(re.findall(r"^([A-Z]+): ?(.*)$", head, re.M))
    return d, body.strip()

def request_params(body):
    return dict(
        model=MODEL, max_tokens=1400,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[{"name": "record", "description": "Record the extracted biographical fields",
                "input_schema": SCHEMA}],
        tool_choice={"type": "tool", "name": "record"},
        messages=[{"role": "user", "content": body or "(no content)"}],
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", type=int, default=0, help="run N bios synchronously and exit")
    a = ap.parse_args()
    client = anthropic.Anthropic()
    files = sorted(glob.glob(str(IN_DIR / "*.txt")))
    print(f"input files: {len(files)}", flush=True)

    if a.smoke:
        for f in files[:a.smoke]:
            d, body = meta(f)
            msg = client.messages.create(**request_params(body))
            fields = next((b.input for b in msg.content if b.type == "tool_use"), None)
            u = msg.usage
            print(f"--- {d.get('NAME')}  in={u.input_tokens} out={u.output_tokens} "
                  f"cache_w={getattr(u,'cache_creation_input_tokens',0)} cache_r={getattr(u,'cache_read_input_tokens',0)}")
            print(json.dumps(fields, ensure_ascii=False)[:600])
        return

    idmap, reqs = {}, []
    for i, f in enumerate(files):
        d, body = meta(f)
        cid = f"p{i:05d}"
        idmap[cid] = {"file": os.path.basename(f), "name": d.get("NAME",""), "start": d.get("START",""),
                      "camara": d.get("CAMARA",""), "pat": d.get("PAT",""), "mat": d.get("MAT","")}
        reqs.append(Request(custom_id=cid,
                            params=MessageCreateParamsNonStreaming(**request_params(body))))
    json.dump(idmap, open(OUT_DIR / "bcn_extract_v2_idmap.json", "w"))
    print(f"submitting batch: {len(reqs)} requests", flush=True)
    batch = client.messages.batches.create(requests=reqs)
    print(f"batch id: {batch.id}", flush=True)
    (OUT_DIR / "bcn_extract_v2_batch_id.txt").write_text(batch.id)

    while True:
        b = client.messages.batches.retrieve(batch.id)
        if b.processing_status == "ended": break
        c = b.request_counts
        print(f"  status={b.processing_status} done={c.succeeded} err={c.errored} proc={c.processing}", flush=True)
        time.sleep(60)

    print("batch ended, collecting...", flush=True)
    recs = []; tin=tout=tcw=tcr=0; ok=err=0
    for res in client.messages.batches.results(batch.id):
        info = idmap.get(res.custom_id, {})
        if res.result.type == "succeeded":
            msg = res.result.message
            u = msg.usage
            tin += u.input_tokens; tout += u.output_tokens
            tcw += getattr(u, "cache_creation_input_tokens", 0) or 0
            tcr += getattr(u, "cache_read_input_tokens", 0) or 0
            fields = next((b.input for b in msg.content if b.type == "tool_use"), None)
            if fields is not None: ok += 1
            recs.append({**info, "fields": fields})
        else:
            err += 1
            recs.append({**info, "fields": None, "error": str(res.result.type)})

    out = OUT_DIR / "bcn_extract_v2.json"
    json.dump(recs, open(out, "w"), ensure_ascii=False)
    # sonnet-5 intro batch pricing: $1.0/M in, $5.0/M out; cache read 0.1x, write 1.25x
    cost = (tin/1e6)*1.0 + (tout/1e6)*5.0 + (tcr/1e6)*0.10 + (tcw/1e6)*1.25
    print(f"\nDONE  ok={ok} err={err}  tokens in={tin} out={tout} cache_w={tcw} cache_r={tcr}")
    print(f"ACTUAL COST ~= ${cost:.2f}  -> {out}", flush=True)

if __name__ == "__main__":
    main()
