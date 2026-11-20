"""Rapports techniques locaux, sans emails complets ni brouillons."""

import re
from datetime import datetime, timezone
from pathlib import Path

from main import ecrire_json


DOSSIER = Path(__file__).with_name("tmp") / "diagnostics_interface"


def enregistrer_rapport(session: str, erreurs: list[dict], version: str,
                        traitement: dict | None = None) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", session):
        raise ValueError("Identifiant de session diagnostic invalide")
    DOSSIER.mkdir(parents=True, exist_ok=True)
    path = DOSSIER / f"{session}.json"
    rapport = {
        "mise_a_jour_utc": datetime.now(timezone.utc).isoformat(),
        "version_traitement": version, "erreurs": erreurs,
    }
    if traitement is not None:
        rapport["traitement"] = traitement
    ecrire_json(path, rapport)
    return path
