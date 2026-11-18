"""Évaluation par nom de fichier, sur une référence distincte des prédictions."""

import argparse
import json
import sys
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from main import ecrire_json
from schemas import CATEGORIES, Annotation, Echec, Resultat


def indexer(lignes: list[dict], schema=None) -> dict[str, dict]:
    index = {}
    for ligne in lignes:
        if schema is not None:
            objet = schema.model_validate(ligne)
        elif ligne.get("statut") == "succes":
            objet = Resultat.model_validate(ligne)
        else:
            objet = Echec.model_validate(ligne)
        nom = objet.fichier
        if nom in index:
            raise ValueError(f"Doublon interdit : {nom}")
        index[nom] = objet.model_dump()
    return index


def evaluer(reference: dict, predictions: list[dict]) -> dict:
    refs = indexer(reference["annotations"], Annotation)
    preds = indexer(predictions)
    if not refs:
        raise ValueError("Référence vide")
    communs = sorted(refs.keys() & preds.keys())
    valides = [nom for nom in communs if preds[nom]["statut"] == "succes"]
    absents = sorted(refs.keys() - preds.keys())
    sans_reference = sorted(preds.keys() - refs.keys())
    echecs = sorted(n for n in preds if preds[n]["statut"] == "erreur")
    vrais = [refs[n]["categorie"] for n in valides]
    predits = [preds[n]["categorie"] for n in valides]
    rapport = classification_report(vrais, predits, labels=CATEGORIES, output_dict=True,
                                    zero_division=0) if valides else None
    erreurs_champs = {}
    for champ in ["categorie", "langue", "priorite", "reponse_necessaire", "a_valider_par_humain"]:
        erreurs_champs[champ] = [
            {"fichier": n, "attendu": refs[n][champ], "predit": preds[n][champ]}
            for n in valides if refs[n][champ] != preds[n][champ]
        ]
    sensibles = [n for n in refs if refs[n]["a_valider_par_humain"]]
    faux_negatifs = [n for n in valides if refs[n]["a_valider_par_humain"]
                     and not preds[n]["a_valider_par_humain"]]
    faux_positifs = [n for n in valides if not refs[n]["a_valider_par_humain"]
                     and preds[n]["a_valider_par_humain"]]
    return {
        "statut_reference": reference["statut"], "origine_reference": reference["origine"],
        "nombre_reference": len(refs), "nombre_predictions": len(preds),
        "nombre_evalues": len(valides), "couverture": len(valides) / len(refs),
        "predictions_manquantes": absents, "predictions_sans_reference": sans_reference,
        "echecs_techniques": echecs,
        "exactitude": float(accuracy_score(vrais, predits)) if valides else None,
        "corrects_sur_reference_totale": sum(a == b for a, b in zip(vrais, predits)) / len(refs),
        "categories_matrice": CATEGORIES,
        "matrice_confusion": confusion_matrix(vrais, predits, labels=CATEGORIES).tolist()
                             if valides else [[0] * len(CATEGORIES) for _ in CATEGORIES],
        "rapport_par_categorie": {c: rapport[c] for c in CATEGORIES} if rapport else None,
        "macro_f1": rapport["macro avg"]["f1-score"] if rapport else None,
        "erreurs_champs": erreurs_champs,
        "sensibles": {"faux_negatifs": faux_negatifs, "faux_positifs": faux_positifs,
                      "non_evalues": sorted(set(sensibles) - set(valides))},
        "limites": "Scores provisoires si référence non validée ; petit lot de développement, "
                   "pas de mesure de généralisation ni de qualité rédactionnelle. "
                   "Matrice : lignes=référence, colonnes=prédiction. Les échecs sont exclus des "
                   "scores conditionnels et restent visibles dans la couverture.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Évaluer les sorties sur les annotations")
    parser.add_argument("--reference", type=Path, default=Path("annotations.json"))
    parser.add_argument("--predictions", type=Path, default=Path("outputs/resultats.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/evaluation.json"))
    args = parser.parse_args(argv)
    try:
        rapport = evaluer(json.loads(args.reference.read_text(encoding="utf-8")),
                          json.loads(args.predictions.read_text(encoding="utf-8")))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        ecrire_json(args.output, rapport)
        print(json.dumps(rapport, ensure_ascii=False, indent=2))
        incomplet = any(rapport[k] for k in ["predictions_manquantes", "predictions_sans_reference", "echecs_techniques"])
        return 1 if incomplet else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Évaluation impossible : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
