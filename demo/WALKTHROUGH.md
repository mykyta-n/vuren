# Vuren · three-minute jury walkthrough

Start the viewer from the repository root with `uv run viewer demo/pitch`. The saved rehearsal follows a fictional gate counter. It runs entirely from the two JSON files, without MCP or model calls. The controls are in Dutch. For the team's submission rehearsal, use `uv run viewer /path/to/saved-run` with the trace and verdict from the same run.

| Time | On screen | What to say |
| --- | --- | --- |
| 0:00–0:25 | **Oordeel → Verloop** | “The export shows double entries every third day. Our question was whether that meant two people passed through the gate. The record IDs let us find the reports. Let's open one and see what was actually counted.” |
| 0:25–0:55 | Under **Bronpassages**, choose **Bekijk beurt 6 en routering**. Read **Vraag van Koning** and **Waarom deze beurt?** | “The Engineer first suggested that the gate opened twice. The King asked the Guardian Keeper because a sealed counter measures physical passages independently of the export.” |
| 0:55–1:25 | Read the full Guardian Keeper reply. Choose **Terug naar Verloop**, then **Bekijk beurt 9 en routering** for Historian. | “The counter registered one passage on day eight. The paper register independently records one visit in that interval. These observations narrow the conclusion to duplicate records on that day.” |
| 1:25–1:55 | In **Debat**, use **Volgende** until turn 12. Read the Engineer's first sentence. Return to **Oordeel → Geschillen (2) · 1 onbeslecht**. | “The Engineer retracts the two-passage explanation. That disagreement is marked *Beslecht*. Retransmission and duplicate import are still competing explanations. That dispute remains *Onbeslecht*.” |
| 1:55–2:30 | Select **Mechanisme · open**. Show **Herstelplan**, then **Risico’s en mitigaties**. | “We leave the mechanism open. First preserve both rows. Then compare transmission and import times. Automatically deleting a row could erase a genuine visit, so keep the originals and check them against the independent counter.” |
| 2:30–3:00 | Select **Verloop** again and show **Voorspelling**. | “The King assigns 80% confidence to the observed pattern. Day eleven is a conditional forecast if the pattern continues. The independent sources changed the proposed explanation and the decision about what to do next.” |

**For the real run:** choose a claim with two sources, open the linked turns, and read the actual follow-up or correction. Use the record IDs, confidence, outcome and forecast from that run. An unresolved mechanism is a legitimate conclusion. For older verdicts, **Vermeldingen in het debat** opens turns containing the cited ID. Read the full reply to judge what the mention supports.

## Verify the demo

From the repository root, run the optional browser check with Node, Playwright and Chromium installed:

```sh
node tests/pitch_viewer.cjs
```

The check starts the actual Python viewer on a free loopback port. It copies the synthetic fixture into a temporary directory, publishes successive live snapshots and tests playback, passage navigation, run isolation, a failed run, older files, and literal markup in source text. It also exercises mobile navigation. Set `PYTHON` to select a Python executable and `CHROME_PATH` to use an installed Chrome or Chromium. Playwright can be installed separately from the Council:

```sh
pitch_tools="$(mktemp -d)"
npm install --prefix "$pitch_tools" playwright
"$pitch_tools/node_modules/.bin/playwright" install chromium
NODE_PATH="$pitch_tools/node_modules" node tests/pitch_viewer.cjs
```
