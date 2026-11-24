const dossier = document.getElementById("dossier");
const verdictrol = document.getElementById("verdictrol");
const hoofdknoop = document.getElementById("open-dossier");
const vorigeStap = document.getElementById("replay-vorige");
const volgendeStap = document.getElementById("replay-volgende");
const replayStatus = document.getElementById("replay-status");
const openVerdictrol = document.getElementById("open-verdictrol");
let stappen = [];
let stapIndex = -1;

function gaNaarStap(index) {
  if (index < 0 || index >= stappen.length || index === stapIndex) return;
  stapIndex = index;
  const stap = stappen[index];
  toonSpreekwolk(stap);
  vorigeStap.disabled = index === 0;
  volgendeStap.disabled = index === stappen.length - 1;
  openVerdictrol.hidden = !volgendeStap.disabled;
  // A newly disabled arrow would otherwise drop keyboard focus.
  if (document.activeElement === vorigeStap && vorigeStap.disabled) volgendeStap.focus();
  if (document.activeElement === volgendeStap && volgendeStap.disabled) openVerdictrol.focus();
}

hoofdknoop.addEventListener("click", () => {
  if (stapIndex >= 0) {
    dossier.showModal();
    return;
  }
  document.querySelector(".poort").classList.add("open");
  document.querySelector(".raadskaart").inert = false;
  hoofdknoop.textContent = "Debat en verdict";
  hoofdknoop.setAttribute("aria-haspopup", "dialog");
  vorigeStap.hidden = volgendeStap.hidden = false;
  gaNaarStap(0);
});

vorigeStap.addEventListener("click", () => gaNaarStap(stapIndex - 1));
volgendeStap.addEventListener("click", () => gaNaarStap(stapIndex + 1));
openVerdictrol.addEventListener("click", () => verdictrol.showModal());
document.addEventListener("keydown", event => {
  if (stapIndex < 0 || dossier.open || verdictrol.open || event.altKey || event.metaKey || event.ctrlKey) return;
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  event.preventDefault();
  gaNaarStap(stapIndex + (event.key === "ArrowLeft" ? -1 : 1));
});

async function laadReplay() {
  try {
    const [trace, verdict] = await Promise.all(["trace.json", "verdict.json"].map(async pad => {
      const antwoord = await fetch(pad, { cache: "no-store" });
      if (!antwoord.ok) throw new Error(pad);
      return antwoord.json();
    }));
    if (trace.status !== "klaar" || !trace.run_id || trace.run_id !== verdict.run_id) {
      throw new Error("Geen overeenkomende bestanden voor een afgerond debat");
    }
    const verdictTekst = verdict.samenvatting?.trim();
    const heeftVerdict = verdictTekst && verdictTekst !== "TODO";
    const koningsbericht = trace.beurten.findLast(beurt =>
      beurt.soort === "bericht" && beurt.spreker === "koning" && beurt.tekst?.trim());
    if (!heeftVerdict && !koningsbericht) throw new Error("Geen verdict of koningssamenvatting");
    stappen = trace.beurten.filter(beurt => plaatsen.some(plaats => plaats.dataset.rol === beurt.spreker)
      && (beurt.soort === "bericht" && beurt.tekst?.trim()
        || beurt.soort === "routering" && beurt.aan && beurt.vraag?.trim()));
    if (!stappen.length) throw new Error("Geen debatstappen");
    render(trace, heeftVerdict ? verdict : null);
    if (!heeftVerdict) {
      document.getElementById("verdictrol-titel").textContent = "Opgenomen koningssamenvatting";
      document.getElementById("rol-inhoud").innerHTML = opmaakAntwoord(koningsbericht.tekst);
      openVerdictrol.setAttribute("aria-label", "Open de koningssamenvatting");
      openVerdictrol.title = "Open de koningssamenvatting";
    }
    hoofdknoop.disabled = false;
  } catch {
    replayStatus.textContent = "Geen afgerond debat met een verdict of koningssamenvatting gevonden.";
    replayStatus.hidden = false;
  }
}
laadReplay();
