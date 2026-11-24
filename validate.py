"""Toets de schema's, spelregels en bronverwijzingen. Start met `uv run validate`."""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parent
# Modellen schrijven ID's soms met een speciaal koppelteken (bv. U+2011): dat faalt op het schema.
RARE_STREEP = re.compile(r"\b(ARC|ENG|GUA|HIS|ORA|BEA)[‐‑‒–—―−]([0-9]{3})\b")
RECORD_ID = re.compile(r"\b(?:ARC|ENG|GUA|HIS|ORA|BEA)-[0-9]{3}\b")
ROLLEN = ("archmage", "engineer", "guardian_keeper", "historian", "oracle", "beast_master")
BEURTENBUDGET = 10
GEDEELTELIJK = "gedeeltelijk_na_broncontrole"


def spelregels(trace):
    """Controleer het beurtenbudget, de routering en toegang tot de eigen bron."""
    fout, toegewezen, aantal = [], None, 0
    gelezen, gesproken = set(), set()
    for b in trace["beurten"]:
        if b["soort"] == "routering":
            toegewezen = b["aan"] if b["spreker"] == "koning" else None
        elif b["soort"] in {"toolcall", "bestand"}:
            rol = b["spreker"]
            if b["soort"] == "toolcall":
                try:
                    url = urlsplit(b["pad"])
                    eigen_bron = url.path.rstrip("/").endswith(f"/{rol}/mcp")
                except ValueError:
                    eigen_bron = False
            else:
                bron = Path(b["bestand"])
                eigen_bron = bool(bron.parts) and bron.parts[0] == rol and ".." not in bron.parts
            if rol not in trace["raadsleden"] or not eigen_bron:
                fout.append(f"trace.json: beurt {b['nr']} ({rol}) raadpleegt geen eigen Kennisbron")
            else:
                gelezen.add(rol)
        elif b["soort"] == "bericht" and b["spreker"] in ROLLEN:
            rol = b["spreker"]
            aantal += 1
            gesproken.add(rol)
            if toegewezen != rol:
                fout.append(f"trace.json: beurt {b['nr']} ({rol}) heeft geen Routering van de Koning naar die Rol ervoor")
            if rol not in gelezen:
                fout.append(f"trace.json: beurt {b['nr']} ({rol}) heeft geen eerdere eigen bronraadpleging")
            toegewezen = None
    if aantal > BEURTENBUDGET:
        fout.append(f"trace.json: {aantal} Raadslid-beurten, het Beurtenbudget is {BEURTENBUDGET}")
    if len(gesproken) < 3:
        fout.append("trace.json: voor de opdracht moeten minimaal drie Rollen bijdragen")
    return fout


def normaliseer_citaat(tekst):
    return " ".join(RARE_STREEP.sub(r"\1-\2", tekst).split())


def bewijsfouten(verdict, trace):
    """Controleer herkomst van de record-ID's en letterlijke bronpassages."""
    berichten = {
        b["nr"]: (b["spreker"], normaliseer_citaat(b["tekst"]))
        for b in trace["beurten"] if b["soort"] == "bericht" and b["spreker"] in trace["raadsleden"]
    }
    record_ids = {record for _, tekst in berichten.values() for record in RECORD_ID.findall(tekst)}
    oorzaken = [(f"oorzaak.{veld}", verdict["oorzaak"][veld]) for veld in ("ingreep", "mechanisme", "verloop")]
    onderdelen = [*oorzaken, ("voorspelling", verdict.get("voorspelling", {}))]
    onderdelen.extend((f"acties[{i}]", actie) for i, actie in enumerate(verdict["acties"]))
    onderdelen.extend((f"geschillen[{i}]", geschil) for i, geschil in enumerate(trace["geschillen"]))

    fouten = []
    for onderdeel, inhoud in onderdelen:
        ontbreekt = set(inhoud.get("bewijs", ())) - record_ids
        if ontbreekt:
            fouten.append(f"{onderdeel}: geen Raadslid citeerde {', '.join(sorted(ontbreekt))}")

    for onderdeel, claim in oorzaken:
        if "bronpassages" not in claim:
            continue  # Oudere Verdicts kunnen alleen de record-ID's bevatten.
        passages = claim["bronpassages"]
        if not isinstance(passages, list):
            fouten.append(f"{onderdeel}: bronpassages moet een lijst zijn")
            continue
        gedekt = set()
        for passage in passages:
            if not isinstance(passage, dict) or type(passage.get("nr")) is not int:
                fouten.append(f"{onderdeel}: ongeldige verwijzing naar een debatbeurt")
                continue
            nummer = passage["nr"]
            rol, tekst = berichten.get(nummer, (None, ""))
            quote = passage.get("citaat")
            citaat = normaliseer_citaat(quote) if isinstance(quote, str) else ""
            if rol is None or rol != passage.get("spreker") or not citaat or citaat not in tekst:
                fouten.append(f"{onderdeel}: onjuist citaat of spreker bij beurt {nummer}")
                continue
            gedekt.update(RECORD_ID.findall(citaat))
        ontbreekt = set(claim["bewijs"]) - gedekt
        if ontbreekt:
            fouten.append(f"{onderdeel}: bronpassages dekken {', '.join(sorted(ontbreekt))} niet")
    return fouten


def fouten(naam):
    pad = ROOT / naam
    if not pad.exists():
        return None, [f"{naam} ontbreekt in de root van de repo"]
    try:
        data = json.loads(pad.read_text(encoding="utf-8"))
    except json.JSONDecodeError as fout:
        return None, [f"{naam}: ongeldige JSON op regel {fout.lineno}: {fout.msg}"]
    schema = json.loads((ROOT / "schema" / naam).read_text(encoding="utf-8"))
    return data, [f"{naam}: {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
                  for e in Draft202012Validator(schema).iter_errors(data)]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    verdict, f1 = fouten("verdict.json")
    trace, f2 = fouten("trace.json")
    alle = f1 + f2
    melding = None
    if not f2:
        alle.extend(spelregels(trace))
        if trace.get("status") in ("bezig", "mislukt"):
            alle.append(f"trace.json: de run is {trace['status']}")
    if not f1:
        if RARE_STREEP.search(json.dumps(verdict, ensure_ascii=False)):
            alle.append("verdict.json bevat ID's met een speciaal koppelteken (bv. ORA‑101): vervang het door een gewoon '-'")
        if verdict["samenvatting"].strip().casefold() == "todo":
            alle.append("verdict.json bevat nog het lege sjabloon uit de kit (TODO)")
    if not f1 and not f2:
        if verdict["run_id"] != trace["run_id"]:
            alle.append("run_id van verdict.json en trace.json verschilt: ze moeten uit dezelfde run komen")
        else:
            alle.extend(bewijsfouten(verdict, trace))
            if GEDEELTELIJK in (verdict.get("finalisatie"), trace.get("verdict_finalisatie")):
                melding = "Gedeeltelijk verdict na broncontrole."
                if not any(actie.get("bewijs") for actie in verdict["acties"]):
                    melding += " Het herstelplan bevat alleen algemene voorzorgsmaatregelen."
    for f in alle:
        print("FOUT", f)
    print("GROEN: verdict.json en trace.json zijn geldig." if not alle else f"ROOD: {len(alle)} fout(en).")
    if melding:
        print("LET OP", melding)
    sys.exit(1 if alle else 0)


if __name__ == "__main__":
    main()
