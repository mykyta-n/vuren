# Demoviewer

Speel in de raadszaal een opgeslagen debat af zonder modelcalls. De demoviewer draait standaard op [poort 8104](http://127.0.0.1:8104/). De liveviewer gebruikt standaard poort 8100.

Voer vanuit de projectmap uit

```sh
uv run demo-viewer "/pad/naar/beste-debat"
```

Zonder uv kun je dezelfde demo starten met `python3 viewer.py --demo "/pad/naar/beste-debat"`. De demoviewer gebruikt alleen de standaardbibliotheek van Python.

De map bevat `trace.json` en `verdict.json` van dezelfde afgeronde run. Kopieer beide bestanden ongewijzigd. Je kunt ze ook in deze map `demo-viewer/` zetten en `uv run demo-viewer` uitvoeren. Zonder bestanden in die map speelt dat commando de synthetische repetitie uit `demo/pitch/` af.

Klik op **Start debat** om de poort te openen. Gebruik **<** en **>** of de pijltjestoetsen om de vragen en antwoorden te volgen. **Debat en verdict** opent het dossier. Op de laatste stap verschijnt de verdictrol bij de Koning.

Gebruik `uv run demo-viewer "/pad/naar/beste-debat" --port 8106` als poort 8104 bezet is.
