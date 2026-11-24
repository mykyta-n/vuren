const bediening = document.querySelector(".zaalbediening");
bediening.classList.add("live");
bediening.innerHTML = '<button id="open-dossier" type="button" aria-haspopup="dialog">Debat en verdict</button>';
document.querySelector(".poort").remove();
document.querySelector(".raadskaart").inert = false;

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

async function lus() {
  const [t, v] = await Promise.all([haal("trace.json"), haal("verdict.json")]);
  try {
    if (t && t + (v || "") !== vorige) {
      const trace = JSON.parse(t);
      const verdict = v ? JSON.parse(v) : null;
      const bezig = trace.status === "bezig";
      const beurten = trace.beurten || [];
      renderKamer(trace, beurten, bezig);
      planSpreekwolk(trace, beurten, bezig);
      render(trace, verdict);
      const klaar = trace.status === "klaar" && verdict?.run_id === trace.run_id
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
