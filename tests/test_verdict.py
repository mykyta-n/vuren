import json
import unittest
from copy import deepcopy
from types import SimpleNamespace

from verdict import REVIEW_INSTRUCTIONS, build_verdict


DEBATE = [
    {"nr": 2, "spreker": "engineer", "tekst": "Testmeter A is vervangen (ENG-901)."},
    {"nr": 4, "spreker": "oracle", "tekst": "Volgens mijn proef bleef testmeter A op zijn plaats (ORA-901)."},
]
UNKNOWN_ID = "ENG-999"


def uncertain_result():
    return {
        "verdict": {
            "samenvatting": "De proefgegevens spreken elkaar tegen. De oorzaak blijft onzeker.",
            "oorzaak": {
                "ingreep": {"bewering": "Meter A is vervangen volgens het testrapport.", "bewijs": ["ENG-901"], "zekerheid": 0.5},
                "mechanisme": {"bewering": None, "bewijs": []},
                "verloop": {"bewering": None, "bewijs": []},
            },
            "acties": [{"actie": "Controleer de meter.", "reden": "De verslagen spreken elkaar tegen."}],
            "risicos": [{"risico": "De meting kan afwijken.", "mitigatie": "Vergelijk met een reservemeter."}],
        },
        "geschillen": [{
            "onderwerp": "Vervanging van de testmeter",
            "standpunten": {"engineer": "De meter is vervangen.", "oracle": "Dezelfde meter bleef staan."},
            "uitkomst": None,
            "bewijs": ["ENG-901", "ORA-901"],
        }],
    }


def expected_verdict(result):
    verdict = deepcopy(result["verdict"])
    verdict["run_id"] = "test-run"
    verdict["oorzaak"]["ingreep"]["bronpassages"] = [
        {"nr": 2, "spreker": "engineer", "citaat": DEBATE[0]["tekst"]},
    ]
    return verdict


class FakeKing:
    def __init__(self, *responses, reviews=None):
        self.responses = iter(responses)
        self.prompts = []
        self.review_prompts = []
        self.reviews = iter(reviews) if reviews is not None else None

    async def run(self, *, messages):
        if messages.startswith(REVIEW_INSTRUCTIONS):
            self.review_prompts.append(messages)
            default = {"ingreep": {"fout": None, "passages": [1]}}
            answer = default if self.reviews is None else next(self.reviews)
            return SimpleNamespace(text=answer if isinstance(answer, str) else json.dumps(answer))
        self.prompts.append(messages)
        return SimpleNamespace(text=json.dumps(next(self.responses)))


class VerdictValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_substantive_uncertainty_on_first_response(self):
        result = uncertain_result()
        king = FakeKing(result)

        verdict, disputes = await build_verdict(king, DEBATE, "test-run")

        self.assertEqual(verdict, expected_verdict(result))
        self.assertEqual(disputes, result["geschillen"])
        self.assertEqual(len(king.prompts), 1)

    async def test_mixed_evidence_requires_repair_for_claim_prediction_and_resolution(self):
        for section in ("claim", "prediction", "resolution"):
            with self.subTest(section=section):
                result = uncertain_result()
                if section == "claim":
                    item = result["verdict"]["oorzaak"]["ingreep"]
                elif section == "prediction":
                    item = {"dag": 6, "bewering": "De proef kan zich herhalen.", "bewijs": ["ENG-901"]}
                    result["verdict"]["voorspelling"] = item
                else:
                    item = result["geschillen"][0]
                    item["uitkomst"] = "De meter is vervangen."
                corrected = deepcopy(result)
                item["bewijs"].append(UNKNOWN_ID)
                king = FakeKing(result, corrected)

                verdict, disputes = await build_verdict(king, DEBATE, "test-run")

                self.assertEqual(len(king.prompts), 2)
                self.assertIn(UNKNOWN_ID, king.prompts[1].split("Vorige uitvoer", 1)[0])
                self.assertEqual(verdict, expected_verdict(corrected))
                self.assertEqual(disputes, corrected["geschillen"])

    async def test_all_unknown_evidence_preserves_uncertainty_without_repair(self):
        result = uncertain_result()
        result["verdict"]["oorzaak"]["ingreep"]["bewijs"] = [UNKNOWN_ID]
        result["verdict"]["voorspelling"] = {
            "dag": 6, "bewering": "De proef kan zich herhalen.", "bewijs": [UNKNOWN_ID],
        }
        result["geschillen"][0].update(uitkomst="De meter is vervangen.", bewijs=[UNKNOWN_ID])
        king = FakeKing(result)

        verdict, disputes = await build_verdict(king, DEBATE, "test-run")

        self.assertEqual(verdict["oorzaak"]["ingreep"], {"bewering": None, "bewijs": []})
        self.assertNotIn("voorspelling", verdict)
        self.assertIsNone(disputes[0]["uitkomst"])
        self.assertEqual(disputes[0]["bewijs"], [])
        self.assertEqual(len(king.prompts), 1)

    async def test_null_cause_discards_evidence_and_confidence_without_repair(self):
        result = uncertain_result()
        result["verdict"]["oorzaak"]["mechanisme"] = {
            "bewering": None, "bewijs": ["ENG-901", UNKNOWN_ID], "zekerheid": 0.5,
        }
        king = FakeKing(result)

        verdict, _ = await build_verdict(king, DEBATE, "test-run")

        self.assertEqual(verdict["oorzaak"]["mechanisme"], {"bewering": None, "bewijs": []})
        self.assertEqual(len(king.prompts), 1)

    async def test_placeholder_only_text_in_required_verdict_fields_triggers_repair(self):
        paths = (
            ("samenvatting",),
            ("oorzaak", "ingreep", "bewering"),
            ("acties", 0, "actie"),
            ("acties", 0, "reden"),
            ("risicos", 0, "risico"),
            ("risicos", 0, "mitigatie"),
            ("voorspelling", "bewering"),
        )
        for path in paths:
            with self.subTest(path=path):
                result = uncertain_result()
                result["verdict"]["voorspelling"] = {"dag": 6, "bewering": "Een proef.", "bewijs": ["ENG-901"]}
                field = result["verdict"]
                for key in path[:-1]:
                    field = field[key]
                field[path[-1]] = "TODO" if path == ("samenvatting",) else " **tBd.** "
                king = FakeKing(result, uncertain_result())

                verdict, _ = await build_verdict(king, DEBATE, "test-run")

                self.assertEqual(len(king.prompts), 2)
                self.assertEqual(verdict["samenvatting"], uncertain_result()["verdict"]["samenvatting"])

    async def test_second_invalid_response_fails_without_third_call(self):
        first = uncertain_result()
        first["verdict"]["samenvatting"] = "TODO"
        second = uncertain_result()
        second["verdict"]["oorzaak"]["ingreep"]["bewijs"].append(UNKNOWN_ID)
        king = FakeKing(first, second)

        with self.assertRaisesRegex(ValueError, "after one repair attempt") as raised:
            await build_verdict(king, DEBATE, "test-run")

        self.assertEqual(len(king.prompts), 2)
        self.assertIn(UNKNOWN_ID, str(raised.exception.__cause__))

    async def test_empty_identical_and_abstaining_positions_require_repair(self):
        for left, right in (
            ("De meter is vervangen.", " TODO "),
            ("De meter bleef staan.", "DE METER  BLEEF STAAN!"),
            ("De meter is vervangen.", "De Oracle weet het niet en neemt geen standpunt in over de meter."),
            ("Ik weet het niet.", "I don't know."),
        ):
            with self.subTest(left=left, right=right):
                invalid = uncertain_result()
                invalid["geschillen"][0]["standpunten"] = {"engineer": left, "oracle": right}
                king = FakeKing(invalid, uncertain_result())
                _, disputes = await build_verdict(king, DEBATE, "test-run")
                self.assertEqual(disputes, uncertain_result()["geschillen"])
                self.assertEqual(len(king.prompts), 2)

    async def test_uncertain_position_with_a_concrete_disagreement_is_accepted(self):
        result = uncertain_result()
        result["geschillen"][0]["standpunten"]["oracle"] = (
            "Ik weet het niet zeker, maar volgens mijn proef bleef de meter staan."
        )
        king = FakeKing(result)
        _, disputes = await build_verdict(king, DEBATE, "test-run")
        self.assertEqual(disputes, result["geschillen"])
        self.assertEqual(len(king.prompts), 1)

    async def test_mixed_citations_for_recovery_action_require_repair(self):
        invalid = uncertain_result()
        invalid["verdict"]["acties"][0]["bewijs"] = ["ENG-901", UNKNOWN_ID]
        king = FakeKing(invalid, uncertain_result())
        verdict, _ = await build_verdict(king, DEBATE, "test-run")
        self.assertEqual(len(king.prompts), 2)
        self.assertIn("verdict.acties[0].bewijs", king.prompts[1].split("Vorige uitvoer", 1)[0])
        self.assertEqual(verdict["acties"], uncertain_result()["verdict"]["acties"])

    async def test_swapped_real_ids_are_repaired_using_the_correct_turns(self):
        debate = [DEBATE[0], {"nr": 4, "spreker": "oracle", "tekst": "Elke test begon met een bel (ORA-901)."}]
        correct = uncertain_result()
        correct["geschillen"] = []
        correct["verdict"]["oorzaak"]["verloop"] = {"bewering": "Bij elke test klonk een bel.", "bewijs": ["ORA-901"]}
        swapped = deepcopy(correct)
        swapped["verdict"]["oorzaak"]["ingreep"]["bewijs"] = ["ORA-901"]
        swapped["verdict"]["oorzaak"]["verloop"]["bewijs"] = ["ENG-901"]
        accepted = {
            "ingreep": {"fout": None, "passages": [1]},
            "verloop": {"fout": None, "passages": [2]},
        }
        rejected = deepcopy(accepted)
        rejected["ingreep"]["fout"] = "De bel beschrijft het begin van de test. Beurt 2 beschrijft de vervanging."
        rejected["verloop"]["fout"] = "De vervanging zegt niets over het ritme. Beurt 4 beschrijft de bel."
        king = FakeKing(swapped, correct, reviews=[rejected, accepted])

        verdict, _ = await build_verdict(king, debate, "test-run")

        inputs = json.loads(king.review_prompts[0].removeprefix(REVIEW_INSTRUCTIONS))
        self.assertEqual(inputs["claims"]["ingreep"]["bewijs"], ["ORA-901"])
        self.assertEqual(inputs["debat"], debate)
        self.assertEqual(inputs["bronpassages"][0], {
            "passage": 1, "nr": 2, "spreker": "engineer", "citaat": debate[0]["tekst"],
        })
        self.assertIn("Beurt 2", king.prompts[1])
        self.assertIn("Beurt 4", king.prompts[1])
        self.assertIn(debate[0]["tekst"], king.prompts[1])
        self.assertEqual(len(king.prompts), 2)
        self.assertEqual(len(king.review_prompts), 2)
        for field, turn in zip(("ingreep", "verloop"), debate):
            self.assertEqual(verdict["oorzaak"][field]["bronpassages"], [
                {"nr": turn["nr"], "spreker": turn["spreker"], "citaat": turn["tekst"]},
            ])

    async def test_false_approval_without_verifiable_evidence_fails_after_repair(self):
        for passages in (
            [],
            [{"nr": 4, "citaat": DEBATE[0]["tekst"]}],
            [999],
            [True],
            [2],
        ):
            with self.subTest(passages=passages):
                review = {"ingreep": {"fout": None, "passages": passages}}
                king = FakeKing(uncertain_result(), uncertain_result(), reviews=[review, review])
                with self.assertRaisesRegex(ValueError, "after one repair attempt"):
                    await build_verdict(king, DEBATE, "test-run")
                self.assertEqual(len(king.prompts), 2)
                self.assertEqual(len(king.review_prompts), 2)

    async def test_abstaining_on_all_causes_skips_review(self):
        result = uncertain_result()
        result["verdict"]["oorzaak"]["ingreep"] = {"bewering": None, "bewijs": []}
        king = FakeKing(result, reviews=[])
        verdict, _ = await build_verdict(king, DEBATE, "test-run")
        self.assertEqual(king.review_prompts, [])
        self.assertEqual(verdict["oorzaak"], result["verdict"]["oorzaak"])

    async def test_compound_claim_requires_passages_for_every_citation(self):
        result = uncertain_result()
        result["verdict"]["oorzaak"]["ingreep"].update(
            bewering="De Engineer meldt een vervanging, maar Oracle zegt dat de meter bleef staan.",
            bewijs=["ENG-901", "ORA-901"],
        )
        incomplete = {"ingreep": {"fout": None, "passages": [1]}}
        complete = {"ingreep": {"fout": None, "passages": [1, 2]}}
        king = FakeKing(result, result, reviews=[incomplete, complete])
        verdict, _ = await build_verdict(king, DEBATE, "test-run")
        self.assertIn("lacks source passages for ORA-901", king.prompts[1])
        self.assertEqual(len(verdict["oorzaak"]["ingreep"]["bronpassages"]), 2)

    async def test_passage_uses_trace_text_and_handles_a_record_heading(self):
        debate = [
            {"nr": 2, "spreker": "engineer", "tekst": "**ENG‑901**\n\nMeter A bleef op zijn plaats."},
            DEBATE[1],
        ]
        result = uncertain_result()
        result["verdict"]["oorzaak"]["ingreep"]["bewering"] = "Meter A bleef op zijn plaats."
        king = FakeKing(result)

        verdict, _ = await build_verdict(king, debate, "test-run")

        self.assertEqual(verdict["oorzaak"]["ingreep"]["bronpassages"], [
            {"nr": 2, "spreker": "engineer", "citaat": "**ENG-901** Meter A bleef op zijn plaats."},
        ])

    async def test_non_json_review_has_its_own_retry(self):
        result = uncertain_result()
        wrapped_review = 'Resultaat:\n```json\n{"ingreep":{"fout":null,"passages":[1]}}\n```'
        king = FakeKing(result, reviews=["Geen bruikbaar antwoord.", wrapped_review])

        verdict, _ = await build_verdict(king, DEBATE, "test-run")

        self.assertEqual(verdict, expected_verdict(result))
        self.assertEqual(len(king.prompts), 1)
        self.assertEqual(len(king.review_prompts), 2)

    async def test_bewaart_getoetst_bewijs_als_herstel_ook_mislukt(self):
        draft = uncertain_result()
        draft["verdict"]["samenvatting"] = "Een onbewezen oorzaak is zeker."
        draft["verdict"]["oorzaak"]["mechanisme"] = {
            "bewering": "Een ongetoetste puls veroorzaakte de storing.", "bewijs": ["ORA-901"],
        }
        review = {
            "ingreep": {"fout": None, "passages": [1]},
            "mechanisme": {"fout": "Dit record ondersteunt die oorzaak niet.", "passages": [2]},
        }
        king = FakeKing(draft, draft, reviews=[review, review])

        verdict, disputes = await build_verdict(king, DEBATE, "test-run")

        self.assertEqual(verdict["finalisatie"], "gedeeltelijk_na_broncontrole")
        self.assertEqual(verdict["run_id"], "test-run")
        self.assertEqual(verdict["oorzaak"]["ingreep"], expected_verdict(draft)["oorzaak"]["ingreep"])
        self.assertEqual(verdict["oorzaak"]["mechanisme"], {"bewering": None, "bewijs": []})
        self.assertNotIn("onbewezen oorzaak", json.dumps(verdict))
        self.assertNotIn("ongetoetste puls", json.dumps(verdict))
        self.assertEqual(disputes, [])
