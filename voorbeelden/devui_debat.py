"""Voorbeeld: dezelfde Raadsleden als MAF-group chat in de DevUI van Microsoft Agent Framework.

Start met:  uv run --extra devui python voorbeelden/devui_debat.py
Daarna opent http://127.0.0.1:8080: kies "Council (group chat)" en typ een vraag,
of praat apart met één Raadslid. Dit voorbeeld plakt de Kennisbron-bestanden uit
kennisbronnen/<rol>/ in de prompt (geen MCP) en schrijft GEEN trace.json of verdict.json:
het is een speeltuin om de orchestratie te verkennen, niet om in te leveren.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_framework import Agent
from agent_framework.devui import serve
from agent_framework.orchestrations import GroupChatBuilder
from dotenv import load_dotenv

import raadsleden
from council import ROOT, client, instructies, kennisbron_bestanden


def main():
    load_dotenv(ROOT / ".env")
    klein = client("MODEL_KLEIN")
    leden = [Agent(klein, instructies(l, kennisbron_bestanden(l.ROL), None), name=l.ROL, description=l.PERSPECTIEF)
             for l in raadsleden.alle()]

    def om_de_beurt(state):  # vaste volgorde, zoals council.py
        namen = list(state.participants)
        return namen[state.current_round % len(namen)]

    council = GroupChatBuilder(name="Council (group chat)", participants=leden, selection_func=om_de_beurt,
                               max_rounds=2 * len(leden)).build()
    serve(entities=[council, *leden], port=8080, auto_open=True, auth_enabled=False)


if __name__ == "__main__":
    main()
