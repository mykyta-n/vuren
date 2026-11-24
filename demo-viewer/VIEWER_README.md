# Demoviewer

Speel in de raadszaal een opgeslagen debat af zonder modelcalls. De demoviewer draait standaard op [poort 8104](http://127.0.0.1:8104/). De liveviewer gebruikt standaard poort 8100.

Voer vanuit de projectmap uit

```sh
uv run demo-viewer
```

Zonder uv kun je dezelfde demo starten met `python3 viewer.py --demo`. De demoviewer gebruikt alleen de standaardbibliotheek van Python.

Standaard lezen de liveviewer en demoviewer `trace.json` en `verdict.json` uit de projectmap. Gebruik beide bestanden ongewijzigd uit dezelfde afgeronde run. Met `uv run demo-viewer "/pad/naar/beste-debat"` speel je een andere opgeslagen run af. Kies voor de synthetische repetitie expliciet `uv run demo-viewer demo/pitch`.

Klik op **Start debat** om de poort te openen. Gebruik **<** en **>** of de pijltjestoetsen om de vragen en antwoorden te volgen. **Debat en verdict** opent het dossier. Op de laatste stap opent de rol bij de Koning het verdict. Bij een ouder debat met een placeholder toont de rol de opgenomen koningssamenvatting.

Gebruik `uv run demo-viewer "/pad/naar/beste-debat" --port 8106` als poort 8104 bezet is.
