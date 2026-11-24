const bediening = document.querySelector(".zaalbediening");
bediening.classList.add("live");
bediening.innerHTML = `
<div class="zaalacties">
    <button id="start-debat" type="button" disabled>Start debat</button>
    <button id="open-dossier" type="button" aria-haspopup="dialog">Debat en verdict</button>
  </div>
  <p id="startmelding" class="startmelding" role="status"></p>
`;

let vorige = "";
const koning = plaatsen.find(plaats => plaats.dataset.rol === "koning");
let vorigeKeuze = "";
koning.addEventListener("animationend", event => {
  if (event.animationName === "wijs") koning.classList.remove("wijst");
});

function renderKamer(trace, beurten, bezig) {
  const laatste = beurten.at(-1);
  const keuze = beurten.findLast(beurt => beurt.soort === "routering");
  const actief = bezig ? (laatste?.soort === "routering" ? laatste.aan || "koning" : trace.aan_het_woord) : null;
  for (const plaats of plaatsen) {
    plaats.setAttribute("aria-current", String(plaats.dataset.rol === actief));
  }
  const keuzeId = keuze && `${trace.run_id}:${keuze.nr}`;
  if (bezig && keuzeId && keuzeId !== vorigeKeuze && keuze.spreker === "koning") {
    koning.classList.add("wijst");
  }
  vorigeKeuze = keuzeId;
}

let wolkRun;
let wolkNr = 0;
let wolkTimer;
let wolkRij = [];

function speelWolken() {
  toonSpreekwolk(wolkRij.shift());
  wolkTimer = setTimeout(() => {
    wolkTimer = undefined;
    if (wolkRij.length) speelWolken();
  }, 2100);
}

function planSpreekwolk(trace, beurten, bezig) {
  if (wolkRun !== trace.run_id || !bezig) {
    clearTimeout(wolkTimer);
    wolkTimer = undefined;
    wolkRij = [];
    wolkNr = 0;
    wolkRun = trace.run_id;
    toonSpreekwolk(null);
  }
  if (!bezig) return;
  const nieuw = beurten.filter(beurt => beurt.nr > wolkNr
    && (beurt.soort === "bericht" || beurt.soort === "routering"));
  if (!nieuw.length) return;
  wolkRij.push(...(wolkNr ? nieuw : nieuw.slice(-1)));
  wolkNr = nieuw.at(-1).nr;
  if (!wolkTimer) speelWolken();
}

async function haal(pad) {
  try { const r = await fetch(pad, { cache: "no-store" }); return r.ok ? await r.text() : null; } catch { return null; }
}

const startKnop = document.getElementById("start-debat");
const startMelding = document.getElementById("startmelding");
const poort = document.querySelector(".poort");
const raadskaart = document.querySelector(".raadskaart");
let startAanvraag = false;
let startVersie = 0;
let uitvoerstatus = null;
let laatsteTrace = null;

function werkStartknopBij() {
  const gestart = uitvoerstatus && uitvoerstatus.fase !== "wacht";
  const bezig = uitvoerstatus?.fase === "bezig";
  const archief = !uitvoerstatus?.beschikbaar && laatsteTrace;
  const open = Boolean(gestart || archief || laatsteTrace?.status === "bezig");
  poort.classList.toggle("open", open);
  raadskaart.inert = !open;
  startKnop.disabled = startAanvraag || bezig || !uitvoerstatus?.beschikbaar;
  startKnop.textContent = bezig ? "Debat bezig" : "Start debat";
  startKnop.title = uitvoerstatus?.beschikbaar ? "" : "Een nieuw debat vereist een lokale projectmap met modelinstellingen.";
  if (uitvoerstatus?.fase === "mislukt") {
    startMelding.textContent = "Het debat is afgebroken. Controleer de viewerterminal.";
  }
}

startKnop.addEventListener("click", async () => {
  startAanvraag = true;
  startVersie += 1;
  startMelding.textContent = "";
  werkStartknopBij();
  try {
    const respons = await fetch("/start-debat", { method: "POST" });
    if (!respons.ok) throw new Error("Start mislukt");
    uitvoerstatus = await respons.json();
    document.getElementById("open-verdictrol").hidden = true;
  } catch {
    startMelding.textContent = "Het debat kon niet worden gestart. Controleer de viewerterminal.";
  } finally {
    startAanvraag = false;
    werkStartknopBij();
  }
});

async function lus() {
  const versie = startVersie;
  const [t, v, r] = await Promise.all([haal("trace.json"), haal("verdict.json"), haal("/run-status")]);
  try {
    if (!startAanvraag && versie === startVersie) uitvoerstatus = r ? JSON.parse(r) : null;
    laatsteTrace = t ? JSON.parse(t) : null;
    werkStartknopBij();
    const wachtOpNieuweTrace = uitvoerstatus?.fase === "bezig" && laatsteTrace?.run_id === uitvoerstatus.vorige_run;
    if (laatsteTrace && !wachtOpNieuweTrace && t + (v || "") !== vorige) {
      const verdict = v ? JSON.parse(v) : null;
      const bezig = laatsteTrace.status === "bezig";
      const beurten = laatsteTrace.beurten || [];
      renderKamer(laatsteTrace, beurten, bezig);
      planSpreekwolk(laatsteTrace, beurten, bezig);
      render(laatsteTrace, verdict);
      const klaar = laatsteTrace.status === "klaar" && verdict?.run_id === laatsteTrace.run_id
        && verdict.samenvatting?.trim() && verdict.samenvatting.trim() !== "TODO";
      document.getElementById("open-verdictrol").hidden = !klaar;
      const rol = document.getElementById("verdictrol");
      if (!klaar && rol.open) rol.close();
      vorige = t + (v || "");
    }
  } catch { /* bestand half geschreven: volgende ronde opnieuw */ }
  setTimeout(lus, 1500);
}
const dossier = document.getElementById("dossier");
document.getElementById("open-dossier").addEventListener("click", () => dossier.showModal());
document.getElementById("open-verdictrol").addEventListener("click", () => {
  document.getElementById("verdictrol").showModal();
});
lus();
