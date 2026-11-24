import unittest

from validate import bewijsfouten, spelregels


class ArtifactValidationTests(unittest.TestCase):
    def setUp(self):
        roles = ("engineer", "oracle", "historian")
        turns = []
        for role, message in zip(roles, ("ENG‑901: De  meter is vervangen.", "ORA-901: Een meting op dag 8.", "HIS-901: Een archiefnotitie.")):
            nr = len(turns) + 1
            turns.extend([
                {"nr": nr, "spreker": "koning", "soort": "routering", "aan": role},
                {"nr": nr + 1, "spreker": role, "soort": "bestand", "bestand": f"{role}/test.md"},
                {"nr": nr + 2, "spreker": role, "soort": "bericht", "tekst": message},
            ])
        turns.append({"nr": 10, "spreker": "koning", "soort": "bericht", "tekst": "ENG-999"})
        self.trace = {"raadsleden": list(roles), "beurten": turns, "geschillen": []}
        self.claim = {
            "bewering": "De meter werd vervangen.",
            "bewijs": ["ENG-901"],
            "bronpassages": [{"nr": 3, "spreker": "engineer", "citaat": "ENG-901: De meter is vervangen."}],
        }
        self.verdict = {
            "oorzaak": {
                "ingreep": self.claim,
                "mechanisme": {"bewering": None, "bewijs": []},
                "verloop": {"bewering": None, "bewijs": []},
            },
            "acties": [],
        }

    def test_accepts_source_reads_and_normalized_passage(self):
        self.trace["beurten"][1] = {
            "nr": 2, "spreker": "engineer", "soort": "toolcall", "pad": "https://example.invalid/engineer/mcp",
        }

        self.assertEqual(spelregels(self.trace), [])
        self.assertEqual(bewijsfouten(self.verdict, self.trace), [])

    def test_rejects_record_only_cited_by_king(self):
        self.verdict["acties"] = [{"actie": "Controleer de meter.", "bewijs": ["ENG-999"]}]

        self.assertIn("geen Raadslid citeerde ENG-999", " ".join(bewijsfouten(self.verdict, self.trace)))

    def test_rejects_wrong_speaker_turn_or_quote(self):
        original = self.claim["bronpassages"][0]
        for field, value in (("spreker", "oracle"), ("nr", 10), ("citaat", "ENG-901: De meter is verwijderd.")):
            with self.subTest(field=field):
                self.claim["bronpassages"] = [{**original, field: value}]

                self.assertIn("onjuist citaat of spreker", " ".join(bewijsfouten(self.verdict, self.trace)))

    def test_rejects_passages_that_miss_a_cited_record(self):
        self.claim["bewijs"].append("ORA-901")

        self.assertIn("bronpassages dekken ORA-901 niet", " ".join(bewijsfouten(self.verdict, self.trace)))

    def test_rejects_cross_role_reads_and_sources_read_by_the_king(self):
        self.trace["beurten"][1]["bestand"] = "oracle/test.md"
        self.trace["beurten"][4]["spreker"] = "koning"

        errors = spelregels(self.trace)

        self.assertEqual(sum("raadpleegt geen eigen Kennisbron" in error for error in errors), 2)
        self.assertEqual(sum("geen eerdere eigen bronraadpleging" in error for error in errors), 2)

    def test_rejects_human_routing_for_automated_submission(self):
        self.trace["beurten"][0]["spreker"] = "mens"

        self.assertIn("geen Routering van de Koning", " ".join(spelregels(self.trace)))

    def test_requires_three_roles_to_contribute(self):
        self.trace["beurten"].pop(8)

        self.assertIn("minimaal drie Rollen bijdragen", " ".join(spelregels(self.trace)))
