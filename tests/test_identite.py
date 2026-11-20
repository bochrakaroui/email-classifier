"""Régressions de présentation observées lors des appels réels, cas synthétiques."""

import pytest
from pydantic import ValidationError

from schemas import AnalyseModele


def contexte(corps, nom="Alex Martin"):
    return {"nom_affiche": nom, "source_identite": nom + "\n" + corps}


def donnees(texte, entreprise="Groupe Nova"):
    return {
        "categorie": "facturation", "priorite": "moyenne", "langue": "fr",
        "resume": texte, "justification": texte, "reponse_necessaire": True,
        "a_valider_par_humain": False, "cas_sensibles": [],
        "entreprise_expediteur": entreprise,
    }


@pytest.mark.parametrize("prefixe", [
    "Alex Martin", "Alex Martin du Groupe Nova", "Alex Martin de Groupe Nova",
])
def test_ajout_societe_mentionnee_sans_changer_la_demande(prefixe):
    action = "demande une explication sur une facture."
    analyse = AnalyseModele.model_validate(
        donnees(f"{prefixe} {action}"),
        context=contexte("Une demande de facturation.\n\nAlex Martin\nGroupe Nova"),
    )
    assert analyse.resume == f"Alex Martin de Groupe Nova {action}"
    assert analyse.justification == analyse.resume


def test_service_signature_reconcilie_avec_nom_affiche_sans_inventer_de_personne():
    analyse = AnalyseModele.model_validate(
        donnees("Service comptabilité – Groupe Nova demande une explication sur une facture."),
        context=contexte(
            "Un écart sur une facture.\n\nBien à vous,\nService comptabilité – Groupe Nova",
            nom="Comptabilité Fournisseurs",
        ),
    )
    assert analyse.resume == "Comptabilité Fournisseurs de Groupe Nova demande une explication sur une facture."


def test_fonction_signee_retiree_et_negation_conservee():
    texte = "Alex Martin, Directeur financier – Groupe Nova, ne souhaite pas recevoir de démo."
    analyse = AnalyseModele.model_validate(
        donnees(texte), context=contexte(
            "Aucune démo demandée.\n\nCordialement,\nAlex Martin\nDirecteur financier – Groupe Nova"
        ),
    )
    assert analyse.resume == "Alex Martin de Groupe Nova ne souhaite pas recevoir de démo."


@pytest.mark.parametrize("prefixe", ["Alex Martin, Group Finance Director,", "Alex Martin de Group"])
def test_group_dans_titre_ne_devient_pas_un_nom_entreprise(prefixe):
    analyse = AnalyseModele.model_validate(
        donnees(f"{prefixe} demande une démonstration.", entreprise="Group"),
        context=contexte("We are a mid-sized group.\n\nBest,\nAlex Martin\nGroup Finance Director"),
    )
    assert analyse.entreprise_expediteur is None
    assert analyse.resume == "Alex Martin demande une démonstration."


def test_personne_autre_dans_signature_ne_remplace_pas_nom_affiche():
    with pytest.raises(ValidationError, match="nom fourni"):
        AnalyseModele.model_validate(
            donnees("Léa Bernard de Groupe Nova demande une démonstration."),
            context=contexte("Un message transféré.\n\nLéa Bernard – Groupe Nova"),
        )


def test_entreprise_inventee_reste_refusee():
    with pytest.raises(ValidationError, match="explicitement nommée"):
        AnalyseModele.model_validate(
            donnees("Alex Martin de Groupe Nova demande une démo."),
            context=contexte("Une demande. Mon email est alex@groupe-nova.example."),
        )


def test_normalisation_identite_ne_masque_pas_une_seconde_phrase():
    with pytest.raises(ValidationError, match="seule phrase"):
        AnalyseModele.model_validate(
            donnees("Alex Martin demande une démo. Il souhaite un devis."),
            context=contexte("Une demande.\n\nAlex Martin\nGroupe Nova"),
        )


def test_champ_entreprise_manquant_reste_refuse_avec_nom_affiche():
    valeurs = donnees("Alex Martin demande une démonstration.")
    del valeurs["entreprise_expediteur"]
    with pytest.raises(ValidationError, match="Field required"):
        AnalyseModele.model_validate(valeurs, context=contexte("Une demande."))


def test_organisme_deja_nomme_non_duplique_et_identite_nommee_reconnue():
    analyse = AnalyseModele.model_validate(
        donnees("L'expéditeur Marketing Nova propose une liste de prospects.", entreprise="Marketing Nova"),
        context=contexte("Une offre publicitaire.", nom="Marketing Nova"),
    )
    assert analyse.resume == "Marketing Nova propose une liste de prospects."
    assert analyse.entreprise_expediteur is None


def test_formule_generique_seule_sans_nom_connu_reste_refusee():
    with pytest.raises(ValidationError, match="nom fourni"):
        AnalyseModele.model_validate(
            donnees("L'utilisateur demande une démonstration."),
            context=contexte("Une demande.\n\nAlex Martin\nGroupe Nova"),
        )


def test_newsletter_dont_le_nom_contient_deja_organisme_non_dupliquee():
    analyse = AnalyseModele.model_validate(
        donnees("L'équipe Finance Info souhaite partager des actualités.", entreprise="Finance Info"),
        context=contexte("Les actualités de la semaine.\n\nBonne lecture !\nL'équipe Finance Info",
                         nom="Newsletter Finance Info"),
    )
    assert analyse.resume == "Newsletter Finance Info souhaite partager des actualités."
    assert analyse.entreprise_expediteur is None


def test_signature_personne_ne_devient_pas_un_alias_de_service():
    with pytest.raises(ValidationError, match="nom fourni"):
        AnalyseModele.model_validate(
            donnees("Léa Bernard de Groupe Nova demande une démonstration."),
            context=contexte("Une demande.\n\nLéa Bernard – Groupe Nova", nom="Service commercial"),
        )


def test_nom_proche_dans_signature_ne_change_pas_identite():
    with pytest.raises(ValidationError, match="nom fourni"):
        AnalyseModele.model_validate(
            donnees("Alex Martinique – Groupe Nova demande une démo."),
            context=contexte("Un message transféré.\n\nAlex Martinique – Groupe Nova"),
        )
