"""Contrats partagés entre le modèle, l'agent, les fichiers et l'évaluation."""

import re
from typing import Literal, Self, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
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


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class Analyse(StrictModel):
    categorie: Categorie
    priorite: Priorite
    langue: Literal["fr", "en"]
    resume: str = Field(min_length=1, max_length=350)
    justification: str = Field(min_length=1, max_length=400)
    reponse_necessaire: bool
    a_valider_par_humain: bool
    cas_sensibles: list[Signal]

    @field_validator("resume")
    @classmethod
    def verifier_phrase_unique(cls, texte: str) -> str:
        if "\n" in texte or len([p for p in re.split(r"[.!?](?:\s+|$)", texte) if p.strip()]) > 1:
            raise ValueError("Le résumé doit tenir en une seule phrase, sans seconde explication")
        return texte


class Brouillon(StrictModel):
    corps: str = Field(min_length=1, max_length=4000)


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
