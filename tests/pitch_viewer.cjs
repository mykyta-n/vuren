// Run from any directory with Playwright and Chromium available (see demo/WALKTHROUGH.md).
const assert = require("node:assert/strict");
const {spawn} = require("node:child_process");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const readline = require("node:readline");
const {once} = require("node:events");
const {chromium} = require("playwright");

const root = path.resolve(__dirname, "..");
const fixture = path.join(root, "demo", "pitch");
const python = process.env.PYTHON || "python3";

async function run() {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), "vuren-pitch-"));
  const file = name => path.join(temp, name + ".json");
  const write = (name, value) => fs.writeFile(file(name), JSON.stringify(value));
  const load = async name => JSON.parse(await fs.readFile(path.join(fixture, name + ".json"), "utf8"));
  const [trace, verdict] = await Promise.all([load("trace"), load("verdict")]);
  const server = spawn(python, ["-u", "-c", "import viewer; viewer.webbrowser.open = lambda url: False; viewer.main()", temp], {
    cwd: root, env: {...process.env, VIEWER_PORT: "0", PYTHONDONTWRITEBYTECODE: "1"}, stdio: ["ignore", "pipe", "inherit"],
  });
  let browser;
  try {
    const lines = readline.createInterface({input: server.stdout});
    const [banner] = await Promise.race([once(lines, "line"), once(server, "exit").then(() => {throw Error("Viewer failed to start");})]);
    const url = banner.match(/http:\/\/127\.0\.0\.1:\d+\//)[0];
    browser = await chromium.launch({executablePath: process.env.CHROME_PATH || undefined});
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    const click = label => page.getByRole("button", {name: label, exact: true}).click();
    const see = text => page.getByText(text, {exact: true}).first().waitFor();
    const state = value => page.waitForFunction(v => document.querySelector("#state").textContent === v, value);
    const absent = async text => assert.equal(await page.getByText(text, {exact: true}).count(), 0);
    await page.goto(url + "pitch");
    await see("Wachten op het debat");

    // Publish partial snapshots as council.py would, with the browser already open.
    await write("trace", {...trace, status:"bezig", aan_het_woord:"engineer", geschillen:[], beurten:trace.beurten.slice(0,3)});
    await state("Live · Engineer");
    await see("Ronde 1 · Beurt 3");
    await write("trace", {...trace, status:"bezig", aan_het_woord:"guardian_keeper", geschillen:[], beurten:trace.beurten.slice(0,6)});
    await see("Ronde 1 · Beurt 6");
    await state("Live · Guardian Keeper");
    await fs.writeFile(file("trace"), "{");
    await see("Bestand tijdelijk onleesbaar. De viewer probeert opnieuw.");
    await see("Ronde 1 · Beurt 6");
    await write("verdict", verdict);
    await write("trace", trace);
    await state("Opgeslagen run");
    await click("Oordeel");
    await see(verdict.samenvatting);
    await see("Dag 11");
    await click("Geschillen (2) · 1 onbeslecht");
    assert.equal(await page.evaluate(() => document.activeElement.id), "geschillen");
    await see("Beslecht");
    await see("Onbeslecht");
    await see(verdict.risicos[0].mitigatie);
    assert.deepEqual(await page.locator("ol li strong").allTextContents(), verdict.acties.map(a => a.actie));
    await click("Mechanisme · open");
    await see("Onopgeloste claim");
    await click("Verloop");
    await see("Zekerheid volgens de Koning · 80%");
    await see(verdict.oorzaak.verloop.bronpassages[1].citaat);
    await click("Bekijk beurt 6 en routering");
    const selected = page.locator("article.selected");
    assert.ok((await selected.innerText()).includes(trace.beurten[3].reden));
    assert.ok((await selected.innerText()).includes(trace.beurten[3].vraag));
    assert.ok((await selected.innerText()).includes(trace.beurten[5].tekst));
    await click("Terug naar Verloop");
    assert.equal(await page.getByRole("button", {name:"Verloop", exact:true}).getAttribute("aria-pressed"), "true");
    await click("Rungegevens");
    await see("4 / 10 raadslidbeurten");
    console.log("PASS live polling, partial writes, successful verdict, passage → full turn + routing → claim");

    await page.reload();
    await see(verdict.samenvatting);
    await click("Debat");
    await click("Afspelen");
    await page.waitForFunction(() => document.querySelectorAll(".event").length > 0 && document.querySelectorAll(".event").length < 14);
    await click("Pauze");
    const n = await page.locator(".event").count();
    await click("Volgende");
    assert.equal(await page.locator(".event").count(), n + 1);
    await page.getByRole("slider").focus();
    await page.keyboard.press("End");
    await see("Ronde 2 · Beurt 14");
    console.log("PASS saved-run playback, pause, step and keyboard seek");

    const old = structuredClone(verdict);
    for (const slot of Object.values(old.oorzaak)) delete slot.bronpassages;
    old.samenvatting = 'Letterlijke tekst <em data-demo="x">archief</em> & namen';
    old.oorzaak.ingreep.zekerheid = 0;
    delete old.voorspelling;
    const legacyTrace = structuredClone(trace);
    delete legacyTrace.status;
    legacyTrace.beurten[2].tekst += ' <em data-demo="y">letterlijke notitie</em>';
    await write("trace", legacyTrace);
    await write("verdict", old);
    await click("Oordeel");
    await see(old.samenvatting);
    await absent("Dag 11");
    await see("Zekerheid volgens de Koning · 0%");
    await see("Vermeldingen in het debat");
    await click("Engineer · beurt 3");
    assert.ok((await page.locator(".event.selected").innerText()).includes('<em data-demo="y">'));
    assert.equal(await page.locator("[data-demo]").count(), 0);
    console.log("PASS older statusless run, ID mention lookup, optional fields and literal markup");

    // A stale quote must never send the judge to an unrelated turn.
    const stale = structuredClone(verdict);
    stale.oorzaak.ingreep.bronpassages[0].nr = 6;
    await write("verdict", stale);
    await click("Oordeel");
    await see("Deze passage kon niet worden gekoppeld aan de opgegeven beurt.");
    assert.equal(await page.getByRole("button", {name: "Bekijk beurt 6 en routering"}).count(), 0);
    console.log("PASS mismatched passage cannot link to a different role");

    const wrong = {...verdict, run_id:"andere-run", samenvatting:"Verkeerd oordeel"};
    await write("verdict", wrong);
    await click("Oordeel");
    await see("Trace en verdict horen bij verschillende runs.");
    await absent("Verkeerd oordeel");
    await absent(old.samenvatting);
    await write("trace", {...trace, status:"mislukt", beurten:trace.beurten.slice(0,6)});
    await state("Run mislukt");
    await see("De run is mislukt. Het debat bevat de laatst opgeslagen beurten.");
    await click("Bekijk het debat");
    await see("Run mislukt · gedeeltelijk debat");
    await see("Ronde 1 · Beurt 6");
    assert.equal(await page.locator(".event").count(), 6);
    console.log("PASS mismatched pair and failed run with partial trace");

    await write("verdict", verdict);
    await write("trace", trace);
    await state("Opgeslagen run");
    await click("Oordeel");
    await see(verdict.samenvatting);
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await click("Verloop");
    await click("Bekijk beurt 6 en routering");
    await see("Waarom deze beurt?");
    assert.deepEqual(errors, []);
    console.log("PASS mobile evidence navigation, no horizontal overflow or browser errors");

    // The previous verdict may still exist when a new run starts.
    await write("trace", {...trace, run_id:"nieuwe-run", status:"bezig", beurten:[], geschillen:[], aan_het_woord:"koning"});
    await state("Live · Koning");
    assert.equal(await page.locator(".event").count(), 0);
    await click("Oordeel");
    await see("Trace en verdict horen bij verschillende runs.");
    await absent(verdict.samenvatting);
    assert.deepEqual(errors, []);
    console.log("PASS new run resets playback and excludes the previous verdict");

    const partial = {...verdict, acties:[{actie:"Bewaar de bronrecords.", reden:"Voorzorg."}]};
    await write("verdict", partial);
    await write("trace", {...trace, status:"klaar", verdict_finalisatie:"gedeeltelijk_na_broncontrole"});
    await page.goto(url + "pitch");
    await see("Gedeeltelijk verdict na broncontrole. Het herstelplan bevat alleen algemene voorzorgsmaatregelen.");
    await page.setViewportSize({width:1280,height:900});
    await page.goto(url);
    await click("Open de verdictrol");
    await page.locator("#rol-inhoud").getByText("Gedeeltelijk verdict na broncontrole.", {exact:true}).waitFor();
    assert.match(await page.locator("#rol-inhoud").innerText(), /alleen algemene voorzorgsmaatregelen/);
    assert.deepEqual(errors, []);
    console.log("PASS partial verdict and generic recovery warning in both views");
  } finally {
    if (browser) await browser.close();
    server.kill();
    await fs.rm(temp, {recursive:true,force:true});
  }
}
run().catch(error => {console.error(error); process.exitCode = 1;});
