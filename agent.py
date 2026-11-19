"""Parcours d'un email : analyse, invariants métier, puis éventuel brouillon."""

import re
import unicodedata

from llm import ErreurTraitement
from prompts import messages_analyse, messages_brouillon
from redaction import propositions_brouillons
from schemas import Analyse, Resultat, schema_brouillon


def detecter_signaux(email: str) -> list[str]:
    """Filet de sécurité lexical indépendant de la catégorie prédite (FR/EN)."""
    texte = "".join(c for c in unicodedata.normalize("NFKD", email.casefold())
                    if not unicodedata.combining(c))
    regles = {
        "incident_bloquant": r"\bbloquant\b|impossible de se connecter|\bcannot log ?in\b|\bblocking incident\b|\bservice down\b",
        "litige_facturation": r"ecart de montant|prelev\w* (?:en )?double|preleves deux fois|rembours\w*|\b(?:un|cet) avoir\b|\bdouble charg\w*|\brefund\w*|billing dispute|credit note",
        "appel_offres": r"appel d.offres|\brfp\b|request for proposal|\btender\b",
    }
    return [signal for signal, motif in regles.items() if re.search(motif, texte)]


def appliquer_regles(email: str, analyse: Analyse) -> Analyse:
    donnees = analyse.model_dump()
    support_non_urgent = analyse.categorie == "support" and bool(
        re.search(r"pas urgent|not urgent|non.urgent", email, re.IGNORECASE)
    )
    donnees["cas_sensibles"] = sorted(set(analyse.cas_sensibles) | set(detecter_signaux(email)))
    if donnees["cas_sensibles"]:
        donnees["a_valider_par_humain"] = True
    if analyse.categorie == "spam":
        donnees["reponse_necessaire"] = False
        donnees["priorite"] = "basse"
    elif donnees["cas_sensibles"] or analyse.categorie == "demo":
        donnees["priorite"] = "haute"
    elif analyse.categorie == "candidature" or not analyse.reponse_necessaire or support_non_urgent:
        donnees["priorite"] = "basse"
    else:
        donnees["priorite"] = "moyenne"
    return Analyse.model_validate(donnees)


def traiter_email(email: str, fichier: str, llm) -> Resultat:
    if not email.strip():
        raise ErreurTraitement("email_vide", "Le fichier ne contient aucun texte")
    if len(email) > 16000:
        raise ErreurTraitement("email_trop_long", "Email supérieur à 16 000 caractères ; aucune troncature silencieuse")
    analyse = llm.generer(messages_analyse(email), Analyse)
    analyse = appliquer_regles(email, analyse)
    brouillon = None
    if analyse.reponse_necessaire:
        try:
            textes = propositions_brouillons(analyse)
            schema = schema_brouillon(textes)
            brouillon = llm.generer(messages_brouillon(email, analyse, textes), schema).corps
        except ErreurTraitement as exc:
            exc.analyse = analyse
            raise
    return Resultat(fichier=fichier, brouillon=brouillon, **analyse.model_dump())
