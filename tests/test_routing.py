import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import raadsleden
from council import kies_volgende, nieuwe_eigen_records


def routering(rol, vraag):
    return SimpleNamespace(text=json.dumps({
        "aan": rol,
        "vraag": vraag,
        "reden": "Vergelijk onafhankelijke waarnemingen.",
        "open_vragen": ["Waardoor ontstond de afwijking?"],
    }))


class BronvoortgangTest(unittest.TestCase):
    def test_houdt_alleen_nieuwe_eigen_records_bij(self):
        debat = [
            {"nr": 2, "spreker": "engineer", "tekst": "Ik citeer ENG-991 en ORA-992."},
            {"nr": 4, "spreker": "engineer", "tekst": "Alleen ENG‑991 werd opnieuw gevonden."},
            {"nr": 6, "spreker": "oracle", "tekst": "Mijn dagboek bevat ORA-992."},
        ]

        self.assertEqual(nieuwe_eigen_records(debat), {2: ["ENG-991"], 4: [], 6: ["ORA-992"]})


class RouteringTest(unittest.IsolatedAsyncioTestCase):
    async def test_opent_met_een_wijziging_rond_de_eerste_symptomen(self):
        koning = SimpleNamespace(run=AsyncMock())

        keuze = await kies_volgende(koning, [], [], raadsleden.alle())

        self.assertEqual(keuze["aan"], "engineer")
        self.assertIn("wijziging aan de werking", keuze["vraag"])
        self.assertIn("eerste gemelde Desync-symptomen", keuze["vraag"])
        koning.run.assert_not_awaited()

    async def test_vraagt_ontwerpregels_bij_eerste_bronsporen(self):
        koning = SimpleNamespace(run=AsyncMock())
        debat = [{"nr": 3, "spreker": "engineer", "tekst": "Het log ENG-991 meldt een proefwijziging."}]
        beurten = [{"soort": "toolcall", "spreker": "engineer"}]

        keuze = await kies_volgende(koning, debat, beurten, raadsleden.alle())

        self.assertEqual(keuze["aan"], "guardian_keeper")
        self.assertIn("schildspecificatie", keuze["vraag"])
        self.assertIn("#3", keuze["reden"])

        debat.append({"nr": 6, "spreker": "guardian_keeper", "tekst": "GUA-993 beschrijft de proefpoort."})
        beurten.append({"soort": "toolcall", "spreker": "guardian_keeper"})

        keuze = await kies_volgende(koning, debat, beurten, raadsleden.alle())

        self.assertEqual(keuze["aan"], "historian")
        self.assertIn("herstelregel", keuze["vraag"])
        self.assertIn("#6", keuze["reden"])

        debat.append({"nr": 9, "spreker": "historian", "tekst": "HIS-994 beschrijft het proefarchief."})
        beurten.append({"soort": "toolcall", "spreker": "historian"})

        keuze = await kies_volgende(koning, debat, beurten, raadsleden.alle())

        self.assertEqual(keuze["aan"], "oracle")
        self.assertIn("laatste relevante waarneming", keuze["vraag"])
        koning.run.assert_not_awaited()

    async def test_wisselt_van_bron_na_een_beurt_zonder_nieuw_record(self):
        koning = SimpleNamespace(run=AsyncMock(side_effect=[
            routering("engineer", "Kun je nog een log vinden?"),
            routering("archmage", "Wat verandert er vóór en na het tijdstip in de leylijnmetingen?"),
        ]))
        debat = [
            {"nr": 2, "spreker": "engineer", "tekst": "ENG-991 dateert de fictieve ingreep."},
            {"nr": 4, "spreker": "engineer", "tekst": "Ik vind alleen het eerder genoemde ENG-991."},
        ]

        keuze = await kies_volgende(koning, debat, [], raadsleden.alle())

        self.assertEqual(keuze["aan"], "archmage")
        self.assertEqual(koning.run.await_count, 2)
        prompt = koning.run.await_args_list[0].kwargs["messages"]
        context = json.loads(prompt.split("\nInput:\n", 1)[1])
        self.assertNotIn("engineer", context["toegestane_rollen"])
        self.assertIn("leylijnmetingen", context["rollen"]["archmage"])
        self.assertEqual(context["debat"][-1]["nieuwe_eigen_record_ids"], [])

    async def test_kan_terugkeren_na_een_nieuwe_aanwijzing(self):
        koning = SimpleNamespace(run=AsyncMock(return_value=routering(
            "engineer", "Past de gemeten afwijking bij een wijziging in het net?",
        )))
        debat = [
            {"nr": 2, "spreker": "engineer", "tekst": "ENG-991 dateert de fictieve ingreep."},
            {"nr": 4, "spreker": "engineer", "tekst": "Mijn bron geeft geen nieuwe details."},
            {"nr": 6, "spreker": "archmage", "tekst": "ARC-993 geeft een onafhankelijke meting."},
        ]

        keuze = await kies_volgende(koning, debat, [], raadsleden.alle())

        self.assertEqual(keuze["aan"], "engineer")
        koning.run.assert_awaited_once()
