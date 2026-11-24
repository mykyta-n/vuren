"""Toetst verdict.json en trace.json aan de schema's in schema/. Start met `uv run validate`."""
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parent
# Modellen schrijven ID's soms met een speciaal koppelteken (bv. U+2011): dat faalt op het schema.
RARE_STREEP = re.compile("(ARC|ENG|GUA|HIS|ORA|BEA)[‐‑‒–—―−][0-9]{3}")
ROLLEN = ("archmage", "engineer", "guardian_keeper", "historian", "oracle", "beast_master")
BEURTENBUDGET = 10


def spelregels(trace):
    """Beurtenbudget en een Routering vóór elke Raadslid-beurt (spelregels, ticket 20)."""
    fout, toegewezen, aantal = [], None, 0
    for b in trace.get("beurten") or []:
        if b.get("soort") == "routering":
            toegewezen = b.get("aan")
        elif b.get("soort") == "bericht" and b.get("spreker") in ROLLEN:
            aantal += 1
            if toegewezen != b["spreker"]:
                fout.append(f"trace.json: beurt {b.get('nr')} ({b['spreker']}) heeft geen Routering naar die Rol ervoor")
            toegewezen = None
    if aantal > BEURTENBUDGET:
        fout.append(f"trace.json: {aantal} Raadslid-beurten, het Beurtenbudget is {BEURTENBUDGET}")
    return fout


def fouten(naam):
    pad = ROOT / naam
    if not pad.exists():
        return None, [f"{naam} ontbreekt in de root van de repo"]
    data = json.loads(pad.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schema" / naam).read_text(encoding="utf-8"))
    return data, [f"{naam}: {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
                  for e in Draft202012Validator(schema).iter_errors(data)]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    verdict, f1 = fouten("verdict.json")
    trace, f2 = fouten("trace.json")
    alle = f1 + f2 + (spelregels(trace) if trace else [])
    if verdict and trace and verdict.get("run_id") != trace.get("run_id"):
        alle.append("run_id van verdict.json en trace.json verschilt: ze moeten uit dezelfde run komen")
    if verdict and RARE_STREEP.search(json.dumps(verdict, ensure_ascii=False)):
        alle.append("verdict.json bevat ID's met een speciaal koppelteken (bv. ORA‑101): vervang het door een gewoon '-'")
    for f in alle:
        print("FOUT", f)
    if verdict and verdict.get("samenvatting") == "TODO":
        print("LET OP: verdict.json is nog het lege sjabloon uit de kit (TODO). Geldig, maar levert geen punten op.")
    print("GROEN: verdict.json en trace.json zijn geldig." if not alle else f"ROOD: {len(alle)} fout(en).")
    sys.exit(1 if alle else 0)


if __name__ == "__main__":
    main()
