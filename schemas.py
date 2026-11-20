"""Contrats partagés entre le modèle, l'agent, les fichiers et l'évaluation."""

import re
from typing import Literal, Self, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    create_model,
    field_validator,
    model_validator,
)

Categorie = Literal[
    "demo", "question_commerciale", "support", "facturation",
    "partenariat", "candidature", "spam", "autre",
]
CATEGORIES = list(get_args(Categorie))
Priorite = Literal["haute", "moyenne", "basse"]
Signal = Literal["incident_bloquant", "litige_facturation", "appel_offres"]
MAX_TEXTE_ANALYSE = 180

ENTREPRISES_GENERIQUES = {
    "group", "groupe", "company", "entreprise", "société", "societe", "team", "équipe",
    "equipe", "pme", "organisation", "organization", "unknown", "inconnu", "inconnue",
}
VERBE_DEMANDE = (
    r"(?:(?:ne)\s+|n['’])?(?:demande|souhaite|souhaiterait|voudrait|cherche|propose|signale|"
    r"conteste|sollicite|annonce|partage|invite|présente|interroge|envoie|réclame|suggère|"
    r"transmet|décrit|indique|veut|lance|offre|postule|s['’]informe)\b"
)


def entreprise_dans_source(entreprise: str, source: str) -> bool:
    """Une adresse ou un domaine seul ne prouve pas le nom d'une société."""
    source = re.sub(r"\S+@\S+|https?://\S+|\b(?:[\w-]+\.)+[a-zA-Z]{2,}\b", " ", source)
    source = " ".join(source.casefold().split())
    societe = " ".join(entreprise.casefold().split())
    return bool(re.search(r"(?<!\w)" + re.escape(societe) + r"(?!\w)", source))


def prefixes_identite(nom: str, entreprise: str | None, source: str) -> set[str]:
    """Variantes du nom et de la signature explicitement présentes dans l'email."""
    service = bool(re.match(r"(?:comptabilit[eé]|service|[eé]quipe|security team|newsletter|team)\b", nom, re.I))
    candidats = {nom, f"L'expéditeur {nom}", f"L’expéditeur {nom}",
                 f"La société {nom}", f"Le service {nom}"}
    if isinstance(entreprise, str) and entreprise_dans_source(entreprise, source):
        for lien in ("de", "du", "de la", "chez"):
            candidats.add(f"{nom} {lien} {entreprise}")
    # Les variantes ne sont prises que dans le dernier bloc (signature) de la source.
    signature = re.split(r"\n\s*\n", source.strip())[-1]
    lignes = [l.strip() for l in signature.splitlines() if l.strip()]
    nom_dans_signature = any(l.casefold() == nom.casefold() for l in lignes)
    for ligne in lignes:
        nom_en_debut = re.match(r"^" + re.escape(nom) + r"(?=$|\W)", ligne, re.I)
        alias_service = (
            service and isinstance(entreprise, str)
            and entreprise.casefold() in ligne.casefold()
            and re.match(r"(?:(?:l['’])?[eé]quipe|service|comptabilit[eé]|newsletter|team|security)\b", ligne, re.I)
        )
        if nom_en_debut or alias_service:
            candidats.add(ligne)
        if nom_dans_signature and re.search(
            r"direct(?:eur|rice|or)|responsable|\bhead\b|\bchief\b|\bceo\b|\bcfo\b|payable|contr[oô]leur|charg[eé]|associ[eé]|\bmanager\b", ligne, re.I
        ):
            candidats.add(f"{nom}, {ligne}")
    return candidats


def normaliser_phrase(texte: str, identite: str, prefixes: list[str]) -> str:
    """Remplacer seulement l'identité ; conserver la demande et sa négation."""
    for prefixe in prefixes:
        motif = r"^\s*" + re.escape(prefixe).replace(r"\ ", r"\s+") + r"(?=$|[\s,:;])"
        debut = re.match(motif, texte, re.I)
        if debut:
            suite = texte[debut.end():].lstrip(" ,:;–—-")
            if re.match(VERBE_DEMANDE, suite, re.I):
                return identite + " " + suite
    return texte


def normaliser_identite(donnees: dict, contexte: dict) -> dict:
    """Nettoyer l'entreprise, puis mettre les deux phrases au format attendu."""
    if "entreprise_expediteur" not in donnees:
        return donnees  # Le champ manquant reste une erreur de validation.
    nom = contexte.get("nom_affiche", "")
    source = contexte.get("source_identite", "")
    entreprise_initiale = donnees["entreprise_expediteur"]
    entreprise = entreprise_initiale
    if isinstance(entreprise, str):
        societe = entreprise.casefold().strip()
        service = re.match(r"(?:comptabilit[eé]|service|[eé]quipe|security team|newsletter|team)\b", nom, re.I)
        deja_dans_service = service and re.search(
            r"(?<!\w)" + re.escape(societe) + r"(?!\w)", nom.casefold(),
        )
        if societe in ENTREPRISES_GENERIQUES or societe == nom.casefold().strip() or deja_dans_service:
            entreprise = None
    elif entreprise is not None:
        return donnees  # Un type incorrect reste une erreur de validation.

    donnees = dict(donnees)
    donnees["entreprise_expediteur"] = entreprise
    if not nom or (entreprise and not entreprise_dans_source(entreprise, source)):
        return donnees

    identite = nom + (f" de {entreprise}" if entreprise else "")
    candidats = prefixes_identite(nom, entreprise_initiale, source) | {identite}
    prefixes = sorted(candidats, key=len, reverse=True)
    for champ in ("resume", "justification"):
        texte = donnees.get(champ)
        if isinstance(texte, str):
            donnees[champ] = normaliser_phrase(texte, identite, prefixes)
    return donnees


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class Analyse(StrictModel):
    categorie: Categorie
    priorite: Priorite
    langue: Literal["fr", "en"]
    resume: str = Field(
        min_length=1, max_length=MAX_TEXTE_ANALYSE,
        description="Une phrase française brève : identité fournie de l'expéditeur (nom complet et entreprise si connus), puis demande principale.",
    )
    justification: str = Field(
        min_length=1, max_length=MAX_TEXTE_ANALYSE,
        description="Une phrase française brève : identité fournie de l'expéditeur (nom complet et entreprise si connus), puis motif concret de la catégorie selon objet et corps.",
    )
    reponse_necessaire: bool
    a_valider_par_humain: bool
    cas_sensibles: list[Signal]

    @field_validator("resume", "justification")
    @classmethod
    def verifier_phrase_unique(cls, texte: str, info: ValidationInfo) -> str:
        # Une raison sociale comme « S.r.l. » ne termine pas à elle seule la phrase.
        texte_a_verifier = re.sub(
            r"\b(?:[A-Za-z]\.){2,}", lambda m: m.group().replace(".", ""), texte,
        )
        if re.search(r"[\r\n\u2028\u2029]", texte) or len(
            [p for p in re.split(r"[.!?](?:\s+|$)", texte_a_verifier) if p.strip()]
        ) > 1:
            libelle = "Le résumé" if info.field_name == "resume" else "La justification"
            raise ValueError(f"{libelle} doit tenir en une seule phrase, sans retour à la ligne ni seconde explication")
        return texte

    @field_validator("resume", "justification")
    @classmethod
    def verifier_identite_fournie(cls, texte: str, info: ValidationInfo) -> str:
        nom = (info.context or {}).get("nom_affiche", "")
        # Le nom vient des données de l'email, jamais d'une déduction par domaine.
        if nom:
            debut = " ".join(texte.casefold().split())
            attendu = " ".join(nom.casefold().split())
            if not debut.startswith(attendu) or (
                len(debut) > len(attendu) and debut[len(attendu)].isalnum()
            ):
                libelle = "Le résumé" if info.field_name == "resume" else "La justification"
                raise ValueError(f"{libelle} doit commencer par le nom fourni : {nom}")
        return texte


class Brouillon(StrictModel):
    corps: str = Field(min_length=1, max_length=4000)


class AnalyseModele(Analyse):
    """Extraction interne de l'entreprise pour contrôler l'identité des deux phrases."""

    entreprise_expediteur: str | None = Field(
        exclude=True, min_length=1, max_length=100,
        description="Entreprise de l'expéditeur explicitement nommée dans le corps ou le nom affiché, sans fonction ni titre ; null si absente.",
    )

    @model_validator(mode="before")
    @classmethod
    def mettre_en_forme_identite(cls, donnees, info: ValidationInfo):
        if isinstance(donnees, dict):
            return normaliser_identite(donnees, info.context or {})
        return donnees

    @model_validator(mode="after")
    def verifier_entreprise_et_prefixe(self, info: ValidationInfo) -> Self:
        contexte = info.context or {}
        entreprise = self.entreprise_expediteur
        if entreprise:
            source = contexte.get("source_identite", "")
            if not entreprise_dans_source(entreprise, source):
                raise ValueError("L'entreprise doit être explicitement nommée dans l'email, sans déduction par domaine")
            nom = contexte.get("nom_affiche", "")
            if nom:
                prefixe = " ".join(f"{nom} de {entreprise}".casefold().split())
                for champ in ("resume", "justification"):
                    texte = " ".join(getattr(self, champ).casefold().split())
                    if not texte.startswith(prefixe + " "):
                        raise ValueError(
                            f"{champ} doit commencer exactement par « {nom} de {entreprise} » "
                            "puis un verbe, sans fonction ni titre"
                        )
        return self


def schema_brouillon(textes_autorises: list[str]) -> type[Brouillon]:
    """L'enum contraint aussi le texte : le modèle ne peut ajouter une affirmation."""
    return create_model("BrouillonContraint", __base__=Brouillon,
                        corps=(Literal[tuple(textes_autorises)], ...))


class Resultat(Analyse):
    fichier: str
    statut: Literal["succes"] = "succes"
    brouillon: str | None

    @model_validator(mode="after")
    def verifier_coherence(self) -> Self:
        if self.categorie == "spam" and (self.reponse_necessaire or self.brouillon):
            raise ValueError("Un spam ne reçoit jamais de brouillon")
        if self.reponse_necessaire != bool(self.brouillon):
            raise ValueError("Le brouillon doit correspondre à reponse_necessaire")
        if self.cas_sensibles and not self.a_valider_par_humain:
            raise ValueError("Un cas sensible exige une revue humaine")
        return self


class Echec(StrictModel):
    fichier: str
    statut: Literal["erreur"] = "erreur"
    type_erreur: str
    message: str
    analyse: Analyse | None = None


class Annotation(StrictModel):
    fichier: str
    categorie: Categorie
    langue: Literal["fr", "en"]
    priorite: Priorite
    reponse_necessaire: bool
    a_valider_par_humain: bool
    commentaire: str
