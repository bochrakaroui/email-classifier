"""Parcours d'un email : analyse, invariants métier, puis éventuel brouillon."""

import json
import re
import unicodedata
from email import policy
from email.parser import Parser

from llm import ErreurTraitement
from prompts import messages_analyse, messages_brouillon
from redaction import propositions_brouillons
from schemas import MAX_TEXTE_ANALYSE, Analyse, AnalyseModele, Resultat, schema_brouillon


MOTIFS_CATEGORIES = {
    "demo": "demande une démonstration du produit.",
    "question_commerciale": "pose une question avant un éventuel achat.",
    "support": "demande une aide sur l'utilisation ou le fonctionnement du service.",
    "facturation": "formule une demande relative à la facturation ou au paiement.",
    "partenariat": "propose une collaboration ou un apport d'affaires.",
    "candidature": "présente une candidature à un emploi ou un stage.",
    "spam": "envoie un message publicitaire non sollicité ou suspect.",
    "autre": "envoie un message hors des catégories spécialisées.",
}


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


def determiner_priorite(email: str, categorie: str) -> str:
    """Spam/autre bas ; sinon urgence explicite dans l'objet avec un sujet réel."""
    if categorie in {"spam", "autre"}:
        return "basse"
    entetes = Parser(policy=policy.default).parsestr(email, headersonly=True)
    objet = str(entetes.get("Subject", "")).casefold()
    # « Non urgent », « pas urgent » et « not urgent » ne signalent pas une urgence.
    objet = re.sub(
        r"\b(?:non[\s\-‐‑–—]*|(?:pas|not)[\s\-‐‑–—]+)urgent(?:e)?s?\b", " ", objet
    )
    urgence = r"\burgent(?:e)?s?\b"
    if not re.search(urgence, objet):
        return "moyenne"
    sujet = re.sub(r"^(?:\s*(?:re|fw|fwd|tr)\s*:\s*)+", "", objet)
    sujet = re.sub(urgence, " ", sujet)
    # « URGENT » seul, même avec ponctuation ou préfixe de réponse, n'a pas de sujet.
    return "haute" if any(c.isalnum() for c in sujet) else "moyenne"


def appliquer_regles(email: str, analyse: Analyse) -> Analyse:
    donnees = analyse.model_dump()
    donnees["cas_sensibles"] = sorted(set(analyse.cas_sensibles) | set(detecter_signaux(email)))
    if donnees["cas_sensibles"]:
        donnees["a_valider_par_humain"] = True
    if analyse.categorie == "spam":
        donnees["reponse_necessaire"] = False
    donnees["priorite"] = determiner_priorite(email, analyse.categorie)
    return Analyse.model_validate(donnees)


def traiter_email(email: str, fichier: str, llm) -> Resultat:
    if not email.strip():
        raise ErreurTraitement("email_vide", "Le fichier ne contient aucun texte")
    if len(email) > 16000:
        raise ErreurTraitement("email_trop_long", "Email supérieur à 16 000 caractères ; aucune troncature silencieuse")
    messages = messages_analyse(email)
    donnees = json.loads(messages[1]["content"])
    contexte = {
        "nom_affiche": donnees["nom_affiche"],
        "source_identite": donnees["nom_affiche"] + "\n" + donnees["corps"],
    }
    analyse = llm.generer(messages, AnalyseModele, contexte=contexte)
    # Le motif stable évite une paraphrase du résumé ou une inversion de rôle.
    # Sans nom affiché, l'identité extraite de la signature reste dans la phrase du modèle.
    if contexte["nom_affiche"]:
        identite = contexte["nom_affiche"]
        if analyse.entreprise_expediteur:
            identite += f" de {analyse.entreprise_expediteur}"
        justification = f"{identite} {MOTIFS_CATEGORIES[analyse.categorie]}"
        if len(justification) > MAX_TEXTE_ANALYSE:
            raise ErreurTraitement("sortie_invalide", "Identité trop longue pour une justification de 180 caractères")
        analyse = Analyse.model_validate(
            analyse.model_dump() | {"justification": justification}, context=contexte,
        )
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
