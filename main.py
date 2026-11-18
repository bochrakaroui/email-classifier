"""CLI locale : lecture stable, erreurs isolées, sorties possédées par l'application."""

import argparse
import hashlib
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from agent import traiter_email
from llm import DEFAULT_MODEL, OPTIONS, ErreurTraitement, OllamaLLM
from schemas import Echec


def lire_email(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise ErreurTraitement("encodage", "Email illisible : UTF-8 attendu") from exc
    except OSError as exc:
        raise ErreurTraitement("lecture", f"Lecture impossible : {exc.strerror}") from exc


def traiter_lot(paths: list[Path], llm) -> list[dict]:
    resultats = []
    for path in sorted(paths, key=lambda p: p.name):
        try:
            resultat = traiter_email(lire_email(path), path.name, llm)
            resultats.append(resultat.model_dump())
            print(f"[OK] {path.name} : {resultat.categorie}", flush=True)
        except ErreurTraitement as exc:
            resultats.append(Echec(fichier=path.name, type_erreur=exc.code,
                                   message=str(exc), analyse=exc.analyse).model_dump())
            print(f"[ERREUR] {path.name} : {exc}", file=sys.stderr, flush=True)
    return resultats


def ecrire_json(path: Path, contenu) -> None:
    ecrire_texte(path, json.dumps(contenu, ensure_ascii=False, indent=2) + "\n")


def ecrire_texte(path: Path, texte: str) -> None:
    """Remplacement atomique d'un fichier ; pas de transaction sur tout le lot."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     dir=path.parent, prefix=".faktus-", delete=False) as flux:
        temporaire = Path(flux.name)
        try:
            flux.write(texte)
        except BaseException:
            flux.close()
            temporaire.unlink(missing_ok=True)
            raise
    try:
        temporaire.replace(path)
    finally:
        temporaire.unlink(missing_ok=True)


def empreinte(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def empreinte_fichier(path: Path) -> str | None:
    try:
        return empreinte(path.read_bytes())
    except OSError:
        return None  # Un fichier illisible reste une erreur isolée du lot.


def enregistrer_sorties(output: Path, resultats: list[dict], execution: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    dossier = output / "reponses"
    dossier.mkdir(exist_ok=True)
    manifeste = output / "manifest.json"
    anciens = json.loads(manifeste.read_text(encoding="utf-8")) if manifeste.exists() else {}
    if not isinstance(anciens, dict):
        raise ValueError("Manifeste invalide : objet JSON attendu")  # noqa: TRY004
    for nom, digest in anciens.items():
        if Path(nom).name != nom or not nom.endswith("_reponse.txt") or "/" in nom or "\\" in nom:
            raise ValueError("Chemin interdit dans le manifeste")
        path = dossier / nom
        if path.exists() and (path.is_symlink() or empreinte(path.read_bytes()) != digest):
            raise ValueError(f"Brouillon modifié à préserver : {nom}. Déplacez-le avant de relancer.")
    nouveaux = {}
    for resultat in resultats:
        if resultat["statut"] == "succes" and resultat["brouillon"]:
            nom = Path(resultat["fichier"]).stem + "_reponse.txt"
            if Path(nom).name != nom or "/" in nom or "\\" in nom:
                raise ValueError("Nom de fichier de sortie interdit")
            nouveaux[nom] = resultat["brouillon"] + "\n"
    for nom in nouveaux:
        if (dossier / nom).exists() and nom not in anciens:
            raise ValueError(f"Fichier non géré à préserver : {nom}")
    for nom, texte in nouveaux.items():
        ecrire_texte(dossier / nom, texte)
    # Seuls les anciens brouillons enregistrés et inchangés peuvent être supprimés.
    for nom in anciens.keys() - nouveaux.keys():
        (dossier / nom).unlink(missing_ok=True)
    ecrire_json(output / "resultats.json", resultats)
    ecrire_json(output / "execution.json", execution)
    ecrire_json(manifeste, {nom: empreinte((dossier / nom).read_bytes()) for nom in nouveaux})


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tri et brouillons locaux des emails FAKTUS")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args(argv)
    try:
        if args.timeout <= 0:
            raise ValueError("--timeout doit être positif")
        if not args.input.is_dir():
            raise ValueError(f"Dossier d'entrée absent : {args.input}")
        paths = sorted(p for p in args.input.iterdir() if p.is_file() and p.suffix.lower() == ".txt")
        if not paths:
            raise ValueError("Le dossier ne contient aucun email .txt")
        llm = OllamaLLM(args.model, args.host, args.timeout)
        debut = time.perf_counter()
        resultats = traiter_lot(paths, llm)
        echecs = sum(r["statut"] == "erreur" for r in resultats)
        execution = {
            "date_utc": datetime.now(timezone.utc).isoformat(), "modele": args.model,
            "host": args.host, "options": OPTIONS, "timeout_secondes": args.timeout,
            "secondes": round(time.perf_counter() - debut, 3),
            "reussites": len(resultats) - echecs, "echecs": echecs, "appels": llm.appels,
            "entrees_sha256": {p.name: empreinte_fichier(p) for p in paths},
            "prompts_sha256": empreinte_fichier(Path(__file__).with_name("prompts.py")),
        }
        enregistrer_sorties(args.output, resultats, execution)
        print(f"Bilan : {len(resultats) - echecs} réussite(s), {echecs} échec(s).")
        return 1 if echecs else 0
    except (OSError, ValueError) as exc:
        print(f"Erreur de configuration ou d'écriture : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
