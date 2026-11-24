import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import raadsleden
from council import (
    bronstatus, kies_volgende, nieuwe_eigen_records, ontbrekend_bronbewijs, raadslid_antwoord,
)


def routering(rol, vraag, doel="mechanisme", spoor="hoogte van de meting"):
    return SimpleNamespace(text=json.dumps({
        "aan": rol,
        "vraag": vraag,
        "doel": doel,
        "spoor": spoor if rol else None,
        "reden": "Vergelijk onafhankelijke waarnemingen.",
        "open_vragen": ["Waardoor ontstond de afwijking?"],
    }))


class BronvoortgangTest(unittest.TestCase):
    def test_bronstatus_wordt_uit_de_zichtbare_tekst_gehaald(self):
        self.assertEqual(bronstatus("De proefbron mist deze meting.\n**BRONSTATUS:** buiten_bron\n"),
                         ("De proefbron mist deze meting.", "buiten_bron"))
        self.assertEqual(bronstatus("Geen marker, wel onzekerheid."), ("Geen marker, wel onzekerheid.", None))

    def test_spreekwolk_bewaart_antwoord_en_citeert_alleen_zichtbaar_bewijs(self):
        volledig = "De proefpoort registreerde één telling (ENG‑991). Het mechanisme blijft onbekend."
        antwoord = volledig + "\n**SPREEKWOLK:** De proefpoort registreerde één telling (ENG-991).\nBRONSTATUS: gevonden"
        tekst, status, wolk = raadslid_antwoord(antwoord)
        self.assertEqual(tekst, volledig)
        self.assertEqual(status, "gevonden")
        self.assertEqual(wolk, {"tekst": "De proefpoort registreerde één telling.", "bewijs": ["ENG-991"]})

    def test_ongeldige_spreekwolk_laat_antwoord_en_bronstatus_intact(self):
        volledig = "Mijn proefbron mist de telling."
        for regel in ("Een telling (ENG-999).", " ".join(["woord"] * 18), ""):
            with self.subTest(regel=regel):
                antwoord = volledig + "\nSPREEKWOLK: " + regel + "\nBRONSTATUS: buiten_bron"
                self.assertEqual(raadslid_antwoord(antwoord), (volledig, "buiten_bron", None))

    def test_oud_antwoord_en_spreekwolk_zonder_citaat(self):
        volledig = "Mijn proefbron mist de telling."
        self.assertEqual(raadslid_antwoord(volledig), (volledig, None, None))
        self.assertEqual(
            raadslid_antwoord(volledig + "\nBRONSTATUS: onzeker\nSPREEKWOLK: Ik kan de telling niet bevestigen."),
            (volledig, "onzeker", {"tekst": "Ik kan de telling niet bevestigen.", "bewijs": []}),
        )

    def test_negeert_bronstatus_zonder_eigen_bronraadpleging(self):
        beurten = [
            {"soort": "routering", "spoor": "meting"},
            {"soort": "toolcall", "spreker": "oracle"},
            {"soort": "bericht", "spreker": "engineer", "bronstatus": "buiten_bron"},
        ]
        self.assertEqual(ontbrekend_bronbewijs(beurten), {})

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

        debat.append({"nr": 12, "spreker": "oracle", "tekst": "ORA-995 dateert de proef."})
        beurten.append({"soort": "toolcall", "spreker": "oracle"})

        keuze = await kies_volgende(koning, debat, beurten, raadsleden.alle())

        self.assertEqual(keuze["aan"], "engineer")
        self.assertEqual(keuze["doel"], "herstel")
        self.assertIn("veiliggesteld", keuze["vraag"])

        beurten.append({"soort": "routering", **keuze})
        beurten.append({"soort": "toolcall", "spreker": "engineer"})
        debat.append({"nr": 15, "spreker": "engineer", "tekst": "ENG-996 geeft een omkeerbare stap."})

        keuze = await kies_volgende(koning, debat, beurten, raadsleden.alle())

        self.assertEqual(keuze["aan"], "beast_master")
        self.assertEqual(keuze["doel"], "verloop")
        self.assertIn("#12", keuze["vraag"])
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
        self.assertNotIn("engineer", context["rollen_per_vervolgdoel"]["mechanisme"])
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

    async def test_verwerpt_derde_vervolg_voor_hetzelfde_doel(self):
        koning = SimpleNamespace(run=AsyncMock(side_effect=[
            routering("historian", "Is er nog een preciezer interval?"),
            routering("engineer", "Welke herstelstap is gedocumenteerd?", "herstel"),
        ]))
        debat = [
            {"nr": 2, "spreker": "beast_master", "tekst": "BEA-991 meldt een tijd, geen interval."},
            {"nr": 4, "spreker": "oracle", "tekst": "ORA-992 dateert een waarneming, geen interval."},
        ]
        beurten = [
            {"soort": "routering", "aan": "beast_master", "vraag": "Welk interval staat er?", "doel": "mechanisme", "open_vragen": ["Welk interval?"]},
            {"soort": "routering", "aan": "oracle", "vraag": "Kun je het interval afleiden?", "doel": "mechanisme", "open_vragen": ["Welk interval?"]},
        ]

        keuze = await kies_volgende(koning, debat, beurten, raadsleden.alle())

        self.assertEqual(keuze["doel"], "herstel")
        self.assertEqual(koning.run.await_count, 2)

    async def test_verwerpt_derde_lege_bronzoektocht_ook_bij_een_ander_doel(self):
        koning = SimpleNamespace(run=AsyncMock(side_effect=[
            routering("historian", "Staat de meetstand misschien in het archief?", "tegenbewijs", " Meetstand "),
            routering("historian", "Welke ontwerpregel geldt?", "mechanisme", "ontwerpregel"),
        ]))
        debat = [
            {"nr": 3, "spreker": "oracle", "tekst": "Mijn dagboek bevat geen meetstand."},
            {"nr": 6, "spreker": "archmage", "tekst": "Mijn bron bevat deze meetstand niet."},
        ]
        beurten = []
        for rol in ("oracle", "archmage"):
            beurten.extend([
                {"soort": "routering", "aan": rol, "vraag": "Wat was de meetstand?", "doel": "verloop",
                 "spoor": "meetstand", "open_vragen": ["Wat was de meetstand?"]},
                {"soort": "toolcall", "spreker": rol},
                {"soort": "bericht", "spreker": rol, "bronstatus": "geen_treffers"},
            ])

        keuze = await kies_volgende(koning, debat, beurten, raadsleden.alle())

        self.assertEqual(keuze["spoor"], "ontwerpregel")
        self.assertEqual(koning.run.await_count, 2)

    async def test_kan_stoppen_met_open_vragen_na_drie_bronnen(self):
        koning = SimpleNamespace(run=AsyncMock(return_value=routering(None, None, None)))
        debat = [
            {"nr": 2, "spreker": "archmage", "tekst": "ARC-991 geeft een eerste meting."},
            {"nr": 4, "spreker": "oracle", "tekst": "ORA-992 dateert een waarneming."},
            {"nr": 6, "spreker": "beast_master", "tekst": "BEA-993 geeft een tweede waarneming."},
        ]
        beurten = [{"soort": "toolcall", "spreker": b["spreker"]} for b in debat]

        keuze = await kies_volgende(koning, debat, beurten, raadsleden.alle())

        self.assertIsNone(keuze["aan"])
        self.assertEqual(keuze["open_vragen"], ["Waardoor ontstond de afwijking?"])

    async def test_vervolg_na_zes_beurten_heeft_een_letterlijke_bronaanwijzing_nodig(self):
        rollen = ("oracle", "historian", "beast_master", "guardian_keeper", "oracle", "historian")
        debat = [
            {"nr": nr, "spreker": rol, "tekst": f"{rol[:3].upper()}-{900 + nr} noemt een dagmeting."}
            for nr, rol in enumerate(rollen, start=1)
        ]
        beurten = [{"soort": "toolcall", "spreker": b["spreker"]} for b in debat]
        vervolg = routering("archmage", "Wat toont de onafhankelijke meting?")
        fake = {**json.loads(vervolg.text), "bronaanwijzing": {"nr": 6, "citaat": "HIS-906 bevat geen meting."}}
        koning = SimpleNamespace(run=AsyncMock(side_effect=[vervolg, SimpleNamespace(text=json.dumps(fake))]))

        keuze = await kies_volgende(koning, debat, beurten, raadsleden.alle())

        self.assertIsNone(keuze["aan"])
        self.assertEqual(koning.run.await_count, 2)

        fake["bronaanwijzing"]["citaat"] = debat[-1]["tekst"]
        koning.run = AsyncMock(return_value=SimpleNamespace(text=json.dumps(fake)))

        keuze = await kies_volgende(koning, debat, beurten, raadsleden.alle())

        self.assertEqual(keuze["aan"], "archmage")
        self.assertEqual(keuze["bronaanwijzing"], fake["bronaanwijzing"])
        koning.run.assert_awaited_once()

        fake["aan"] = "historian"
        koning.run = AsyncMock(side_effect=[
            SimpleNamespace(text=json.dumps(fake)), routering(None, None, None),
        ])

        keuze = await kies_volgende(koning, debat, beurten, raadsleden.alle())

        self.assertIsNone(keuze["aan"])
        self.assertEqual(koning.run.await_count, 2)
