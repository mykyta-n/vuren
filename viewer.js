"use strict";

const main = document.querySelector("main");
const nav = document.querySelector("nav");
const names = new Map(Object.entries({
  archmage: "Archmage", engineer: "Engineer", guardian_keeper: "Guardian Keeper",
  historian: "Historian", oracle: "Oracle", beast_master: "Beast Master", koning: "Koning", mens: "Mens",
}));
const slots = new Map([["ingreep", "Ingreep"], ["mechanisme", "Mechanisme"], ["verloop", "Verloop"]]);
const recordPattern = /\b[A-Z]{3}[-‐‑‒–—―−]\d{3}\b/g;
const nameOf = role => names.get(role) ?? String(role ?? "");
const canonical = text => String(text ?? "").replace(recordPattern, id => id.replace(/[^A-Z0-9]/, "-"));
const plain = text => canonical(text).replace(/\s+/g, " ").trim();
const records = text => new Set(canonical(text).match(recordPattern) ?? []);
let trace, verdict, snapshot, page = "oordeel", claim = "ingreep", selectedTurn = null;
let cursor = 0, timer = null, requestProblem = "";

function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = String(text);
  if (cls) node.className = cls;
  return node;
}
function button(label, click) {
  const node = el("button", label);
  node.type = "button";
  node.addEventListener("click", click);
  return node;
}
function panel(title) {
  const node = el("section", null, "panel");
  node.append(el("h2", title));
  return node;
}
function rich(text, tag = "p") {
  const node = el(tag, null, "prose");
  const value = String(text ?? "");
  let offset = 0;
  for (const match of value.matchAll(recordPattern)) {
    node.append(value.slice(offset, match.index), el("span", match[0], "record"));
    offset = match.index + match[0].length;
  }
  node.append(value.slice(offset));
  return node;
}
function chips(ids) {
  const row = el("div", null, "chips");
  for (const id of ids ?? []) row.append(el("code", id, "record"));
  return row;
}
const turns = () => trace?.beurten ?? [];
const live = () => trace?.status === "bezig";
const failed = () => trace?.status === "mislukt";
const roleTurn = b => b.soort === "bericht" && trace.raadsleden.includes(b.spreker);
function routingFor(turn) {
  const index = turns().indexOf(turn);
  for (let i = index - 1; i >= 0; i--) {
    const prior = turns()[i];
    if (prior.soort === "routering") return prior.aan === turn.spreker ? prior : null;
    if (roleTurn(prior)) break;
  }
  return null;
}
function stop() {
  clearInterval(timer);
  timer = null;
}
function switchPage(next) {
  stop();
  page = next;
  draw();
}
nav.addEventListener("click", event => {
  const target = event.target.closest("button[data-page]");
  if (target) {
    switchPage(target.dataset.page);
    main.scrollIntoView({block: "start"});
  }
});
function jump(turn) {
  selectedTurn = turn.nr;
  cursor = turns().indexOf(turn) + 1;
  switchPage("debat");
  const node = document.querySelector(".event.selected");
  node?.focus();
  node?.scrollIntoView({block: "center"});
}
function chooseClaim(key) {
  claim = key;
  draw();
  document.querySelector('.tabs [aria-pressed="true"]')?.focus();
}
function drawClaim() {
  const node = panel("Oorzaak");
  const controls = el("div", null, "row tabs");
  for (const [key, label] of slots) {
    const unknown = !verdict.oorzaak?.[key]?.bewering;
    const btn = button(label + (unknown ? " · open" : ""), () => chooseClaim(key));
    btn.setAttribute("aria-pressed", String(claim === key));
    controls.append(btn);
  }
  node.append(controls);
  const slot = verdict.oorzaak?.[claim];
  if (!slot?.bewering) {
    node.append(el("span", "Onopgeloste claim", "badge open"), el("p", "De Raad heeft voor dit onderdeel onvoldoende bewijs."));
    return node;
  }
  node.append(rich(slot.bewering));
  if (typeof slot.zekerheid === "number") node.append(el("small", "Zekerheid volgens de Koning · " + Math.round(slot.zekerheid * 100) + "%"));
  node.append(chips(slot.bewijs));
  if (slot.bronpassages?.length) {
    node.append(el("h3", "Bronpassages"));
    for (const p of slot.bronpassages) {
      const block = el("div", null, "passage");
      const turn = turns().find(t => t.nr === p.nr && t.spreker === p.spreker && roleTurn(t));
      block.append(el("strong", nameOf(p.spreker) + " · beurt " + p.nr), rich(p.citaat, "blockquote"));
      if (turn && plain(p.citaat) && plain(turn.tekst).includes(plain(p.citaat))) {
        block.append(button("Bekijk beurt " + p.nr + " en routering", () => jump(turn)));
      } else {
        block.append(el("small", "Deze passage kon niet worden gekoppeld aan de opgegeven beurt.", "danger"));
      }
      node.append(block);
    }
  } else {
    node.append(el("h3", "Vermeldingen in het debat"), el("small", "Dit oordeel bevat geen bronpassages. Open een vermelding om de context te lezen."));
    const cited = new Set((slot.bewijs ?? []).map(canonical));
    const matches = turns().filter(t => roleTurn(t) && [...records(t.tekst)].some(id => cited.has(id)));
    const links = el("div", null, "row");
    for (const t of matches) links.append(button(nameOf(t.spreker) + " · beurt " + t.nr, () => jump(t)));
    node.append(matches.length ? links : el("small", "Geen bijbehorende vermelding gevonden."));
  }
  return node;
}
function disputes() {
  const node = panel("Geschillen");
  node.id = "geschillen";
  node.tabIndex = -1;
  const items = trace.geschillen ?? [];
  if (!items.length) node.append(el("p", "Geen geschillen vastgelegd.", "muted"));
  for (const g of items) {
    const item = el("div", null, "item");
    item.append(el("span", g.uitkomst ? "Beslecht" : "Onbeslecht", "badge" + (g.uitkomst ? "" : " open")), el("h3", g.onderwerp));
    for (const [role, stance] of Object.entries(g.standpunten ?? {})) {
      item.append(el("strong", nameOf(role)), rich(stance));
    }
    if (g.uitkomst) item.append(el("strong", "Uitkomst"), rich(g.uitkomst));
    item.append(chips(g.bewijs));
    node.append(item);
  }
  return node;
}
function outcome() {
  main.append(el("h1", "Oordeel van de Raad"));
  const mismatch = verdict && verdict.run_id !== trace.run_id;
  if (failed() || live() || mismatch || !verdict || !trace.run_id) {
    const reason = failed() ? "De run is mislukt. Het debat bevat de laatst opgeslagen beurten."
      : mismatch ? "Trace en verdict horen bij verschillende runs."
      : live() ? "Het debat loopt. Het oordeel verschijnt na afloop."
      : "Wachten op een verdict voor deze run.";
    main.append(el("p", reason, "notice"), button("Bekijk het debat", () => switchPage("debat")));
    return;
  }
  const summary = rich(verdict.samenvatting);
  summary.classList.add("summary");
  const grid = el("div", null, "grid"), left = el("div", null, "stack"), right = el("div", null, "stack");
  left.append(drawClaim(), disputes());
  const plan = panel("Herstelplan"), list = el("ol");
  for (const a of verdict.acties ?? []) {
    const li = el("li");
    li.append(el("strong", a.actie), rich(a.reden), chips(a.bewijs));
    list.append(li);
  }
  plan.append(list);
  const risks = panel("Risico’s en mitigaties");
  for (const r of verdict.risicos ?? []) {
    const item = el("div", null, "item");
    item.append(el("strong", r.risico), el("small", "Mitigatie"), rich(r.mitigatie));
    risks.append(item);
  }
  right.append(plan, risks);
  if (verdict.voorspelling) {
    const f = verdict.voorspelling, forecast = panel("Voorspelling");
    forecast.append(el("span", "Dag " + f.dag, "badge"), rich(f.bewering), chips(f.bewijs));
    right.append(forecast);
  }
  grid.append(left, right);
  const totals = trace.geschillen ?? [];
  const open = totals.filter(g => !g.uitkomst).length;
  main.append(summary);
  if (totals.length) {
    const link = button("Geschillen (" + totals.length + ") · " + open + " onbeslecht", () => {
      const section = document.getElementById("geschillen");
      section.focus();
      section.scrollIntoView({block: "start"});
    });
    link.className = "dispute-link";
    main.append(link);
  }
  main.append(grid);
}
function routeInfo(route) {
  const node = el("div", null, "passage");
  if (!route) {
    node.append(el("small", "Geen bijbehorende routering vastgelegd."));
  } else {
    node.append(el("strong", "Vraag van " + nameOf(route.spreker)), rich(route.vraag), el("strong", "Waarom deze beurt?"), rich(route.reden));
  }
  return node;
}
function eventCard(t) {
  const selected = selectedTurn === t.nr;
  const node = el("article", null, "event" + (selected ? " selected" : ""));
  node.tabIndex = -1;
  node.append(el("small", "Ronde " + t.ronde + " · Beurt " + t.nr));
  if (t.soort === "routering") {
    node.append(el("h3", nameOf(t.spreker) + (t.aan ? " → " + nameOf(t.aan) : " sluit het debat")));
    if (t.vraag) node.append(rich(t.vraag));
    node.append(el("strong", "Reden"), rich(t.reden));
    if (t.open_vragen?.length) node.append(el("strong", "Open vragen"), rich(t.open_vragen.join("\n")));
  } else if (t.soort === "bericht") {
    node.append(el("h3", nameOf(t.spreker)));
    if (selected && roleTurn(t)) node.append(routeInfo(routingFor(t)));
    node.append(rich(t.tekst));
    if (selected) {
      const back = button("Terug naar " + slots.get(claim), () => {
        selectedTurn = null;
        switchPage("oordeel");
        document.querySelector('.tabs [aria-pressed="true"]')?.focus();
      });
      back.className = "back";
      node.append(back);
    }
  } else {
    node.append(el("h3", nameOf(t.spreker) + " · " + (t.soort === "bestand" ? "Bronbestand" : "Bronoproep")));
    node.append(rich(t.bestand ?? t.tool));
    if (t.pad) node.append(el("small", t.pad));
    if (t.argumenten) node.append(rich(JSON.stringify(t.argumenten)));
  }
  return node;
}
function setCursor(value) {
  cursor = value;
  selectedTurn = null;
  if (cursor >= turns().length) stop();
  draw();
}
function playback() {
  const node = el("div", null, "row playback"), max = turns().length;
  const play = button(timer ? "Pauze" : "Afspelen", () => {
    if (timer) stop();
    else {
      if (cursor >= max) cursor = 0;
      selectedTurn = null;
      timer = setInterval(() => {
        setCursor(Math.min(turns().length, cursor + 1));
        document.querySelector(".event:last-child")?.scrollIntoView({block: "nearest"});
      }, 1400);
    }
    draw();
    document.querySelector(".playback button")?.focus();
  });
  const slider = el("input");
  slider.type = "range"; slider.min = 0; slider.max = max; slider.value = cursor;
  slider.setAttribute("aria-label", "Aantal zichtbare gebeurtenissen");
  const counter = el("output", cursor + " / " + max);
  slider.addEventListener("input", () => { counter.textContent = slider.value + " / " + max; });
  slider.addEventListener("change", () => {
    stop(); setCursor(Number(slider.value));
    document.querySelector(".playback input")?.focus();
  });
  const step = button("Volgende", () => {
    stop(); setCursor(Math.min(max, cursor + 1));
    document.querySelector(".step")?.focus();
  });
  step.className = "step"; step.disabled = cursor >= max;
  play.disabled = !max;
  node.append(play, slider, counter, step);
  return node;
}
function transcript() {
  main.append(el("h1", "Raadsdebat"));
  if (!live()) main.append(playback());
  if (failed()) main.append(el("p", "Run mislukt · gedeeltelijk debat", "notice"));

  const log = el("div", null, "timeline");
  const visible = live() ? turns() : turns().slice(0, cursor);
  for (const t of visible) log.append(eventCard(t));
  if (!visible.length) log.append(el("p", "Nog geen zichtbare beurten.", "muted"));
  main.append(log);
}
function runDetails() {
  main.append(el("h1", "Rungegevens"));
  const grid = el("div", null, "grid"), members = panel("Raadsleden"), checks = panel("Spelregels");
  const table = el("table");
  const head = table.insertRow();
  for (const label of ["Rol", "Berichten", "Bronnen", "ID’s"]) head.append(el("th", label));
  for (const role of [...trace.raadsleden, "koning"]) {
    const events = turns().filter(t => t.spreker === role);
    const messages = events.filter(t => t.soort === "bericht");
    const row = table.insertRow();
    for (const value of [nameOf(role), messages.length, events.filter(t => ["toolcall", "bestand"].includes(t.soort)).length,
      new Set(messages.flatMap(t => [...records(t.tekst)])).size]) row.append(el("td", value));
  }
  members.append(table);
  const msgs = turns().filter(roleTurn);
  const sources = turns().filter(t => ["toolcall", "bestand"].includes(t.soort));
  const missingSource = trace.raadsleden.filter(role => !sources.some(t => t.spreker === role));
  const warnings = [];
  if (missingSource.length) warnings.push("Geen bronoproep of bestand voor " + missingSource.map(nameOf).join(", "));
  if (sources.some(t => t.spreker === "koning")) warnings.push("De Koning heeft een bron geraadpleegd.");
  for (const t of sources) {
    if (t.soort === "bestand" ? !String(t.bestand).startsWith(t.spreker + "/") : !String(t.pad).includes("/" + t.spreker + "/"))
      warnings.push("Controleer het bronpad bij beurt " + t.nr + ".");
  }
  for (const t of msgs) if (!routingFor(t)) warnings.push("Routering ontbreekt voor beurt " + t.nr + ".");
  if (msgs.length > 10) warnings.push("Beurtenbudget overschreden.");
  if (trace.raadsleden.length < 3) warnings.push("Minder dan drie rollen.");
  if (msgs.some(t => [...String(t.tekst).matchAll(recordPattern)].some(m => m[0] !== canonical(m[0]))))
    warnings.push("Sommige vermelde ID’s bevatten een afwijkend koppelteken.");
  checks.append(el("strong", msgs.length + " / 10 raadslidbeurten"));
  for (const note of warnings) checks.append(el("p", note, "notice"));
  if (!warnings.length) checks.append(el("p", "Geen afwijkingen in de geregistreerde routeringen, bronpaden en beurten."));
  const usage = panel("Modelverbruik");
  for (const [model, u] of Object.entries(trace.verbruik ?? {}))
    usage.append(el("p", model + " · " + (u.beurten ?? u.calls) + " beurten · " + (u.invoer ?? 0) + " tokens in · " + (u.uitvoer ?? 0) + " uit"));
  if (!Object.keys(trace.verbruik ?? {}).length) usage.append(el("p", "Geen verbruik geregistreerd."));
  grid.append(members, checks, usage);
  main.append(grid);
}
function draw() {
  main.replaceChildren();
  for (const b of nav.querySelectorAll("button")) {
    if (b.dataset.page === page) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  const state = document.querySelector("#state");
  state.textContent = !trace ? "Wachten op debat" : live() ? "Live" + (trace.aan_het_woord ? " · " + nameOf(trace.aan_het_woord) : "")
    : failed() ? "Run mislukt" : "Opgeslagen run";
  document.querySelector("#run").textContent = trace?.run_id ?? "";
  if (requestProblem) main.append(el("p", requestProblem, "notice"));
  if (!trace) { main.append(el("h1", "Wachten op het debat"), el("p", "Start de Raad of open een opgeslagen run.")); return; }
  if (page === "debat") transcript();
  else if (page === "gegevens") runDetails();
  else outcome();
}
async function readFile(path) {
  const response = await fetch(path, {cache: "no-store"});
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("HTTP " + response.status);
  return response.json();
}
async function poll() {
  try {
    const [t, v] = await Promise.allSettled([readFile("trace.json"), readFile("verdict.json")]);
    const problem = t.status === "rejected" || v.status === "rejected" ? "Bestand tijdelijk onleesbaar. De viewer probeert opnieuw." : "";
    const next = t.status === "fulfilled" ? t.value : trace;
    const nextVerdict = v.status === "fulfilled" ? v.value : null;
    const key = JSON.stringify([next, nextVerdict, problem]);
    if (key !== snapshot) {
      const changed = next?.run_id !== trace?.run_id;
      const previousStatus = trace?.status;
      const followLive = page === "debat" && live() && !changed &&
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 80;
      trace = next;
      verdict = nextVerdict;
      requestProblem = problem;
      if (changed) {
        stop(); selectedTurn = null; claim = "ingreep"; page = live() ? "debat" : "oordeel";
      }
      if (previousStatus !== trace?.status) {
        stop();
        selectedTurn = null;
      }
      if (changed || live() || previousStatus !== trace?.status) cursor = turns().length;
      else cursor = Math.min(cursor, turns().length);
      draw();
      if (followLive && live()) document.querySelector(".event:last-child")?.scrollIntoView({block: "end"});
      snapshot = key;
    }
  } finally { setTimeout(poll, 1000); }
}
poll();
