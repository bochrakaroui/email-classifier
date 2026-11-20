"""Interactions réelles Streamlit/AppTest, transport Ollama simulé uniquement."""

import json
from pathlib import Path
from unittest.mock import patch

import streamlit as st
import pytest
from streamlit.testing.v1 import AppTest

from app import identifiant_email
from tests.test_agent import BROUILLON_AUTORISE, analyse, faux_llm


APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture(autouse=True)
def isoler_rapports_diagnostic(monkeypatch, tmp_path):
    monkeypatch.setattr("diagnostics.DOSSIER", tmp_path / "diagnostics")


def fichier(nom="demande.txt", texte="Subject: Aide\nFrom: lea@example.test\n\nUne question."):
    return nom, texte.encode("utf-8"), "text/plain"


def simulation(monkeypatch, *reponses):
    llm, client = faux_llm(*reponses)
    constructions = []

    def construire():
        constructions.append(True)
        return llm

    monkeypatch.setattr("llm.OllamaLLM", construire)
    return client, constructions


def ouvrir():
    at = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not at.exception
    return at


def charger(at, *fichiers):
    at.file_uploader("fichiers").set_value(list(fichiers)).run()
    assert not at.exception


def test_action_explicite_et_gmail_indisponible(monkeypatch):
    client, constructions = simulation(monkeypatch)
    at = ouvrir()
    assert at.button("analyser").disabled
    charger(at, fichier())
    assert not at.button("analyser").disabled
    assert at.dataframe[0].value["État"].tolist() == ["À analyser"]
    assert client.appels == constructions == []
    at.radio("source").set_value("Gmail de test").run()
    assert not at.exception
    assert "Connexion Gmail non configurée" in [w.value for w in at.warning]
    assert all(b.disabled for b in at.button)
    assert at.file_uploader("fichiers").disabled
    assert client.appels == constructions == []


def test_selection_corrections_et_telechargement_sans_nouvel_appel(monkeypatch):
    client, constructions = simulation(
        monkeypatch, analyse(), BROUILLON_AUTORISE,
        analyse(categorie="question_commerciale", langue="en"), BROUILLON_AUTORISE,
    )
    at = ouvrir()
    charger(at, fichier("a.txt"), fichier("b.txt", "Subject: Pricing\n\nCould you help?"))
    at.button("analyser").click().run()
    assert not at.exception
    assert len(client.appels) == 4 and len(constructions) == 1
    assert at.dataframe[0].value["État"].tolist() == ["Traité", "Traité"]
    assert at.metric[1].value == "2"
    premier, second = list(at.session_state["emails"])
    initial = at.session_state["resultats"][premier]["brouillon"]
    correction = "Bonjour, voici ma correction humaine libre, hors catalogue.\nCordialement."
    at.text_area(f"edition_{premier}").set_value(correction).run()
    assert at.session_state["corrections"][premier] == correction
    assert at.session_state["resultats"][premier]["brouillon"] == initial
    at.selectbox("choix_email").select(second).run()
    assert not at.exception
    assert at.text_area(f"original_{second}").value.endswith("Could you help?")
    assert any("Anglais" in m.value for m in at.markdown)
    with patch("streamlit.download_button", wraps=st.download_button) as telecharger:
        at.selectbox("choix_email").select(premier).run()
        assert at.text_area(f"edition_{premier}").value == correction
        assert telecharger.call_args.kwargs["data"] == correction.encode("utf-8")
        assert telecharger.call_args.kwargs["on_click"] == "ignore"
    at.download_button[0].click().run()
    assert not at.exception
    assert len(client.appels) == 4 and len(constructions) == 1
    assert at.button("analyser").disabled


def test_homonymes_distincts_et_doublon_strict(monkeypatch):
    client, _ = simulation(monkeypatch)
    at = ouvrir()
    a, b = fichier("email.txt", "Version A"), fichier("email.txt", "Version B")
    charger(at, a, b, a)
    assert len(at.session_state["emails"]) == 2
    assert at.dataframe[0].value["Fichier"].nunique() == 2
    assert at.metric[0].value == "2"
    premier, second = list(at.session_state["emails"])
    at.selectbox("choix_email").select(second).run()
    assert at.text_area(f"original_{second}").value == "Version B"
    assert premier != second and not client.appels


def test_changement_contenu_invalide_resultat_et_conserve_ancienne_correction(monkeypatch):
    client, _ = simulation(monkeypatch, analyse(), BROUILLON_AUTORISE, analyse(), BROUILLON_AUTORISE)
    at = ouvrir()
    ancien = fichier("email.txt", "Première demande")
    nouveau = fichier("email.txt", "Une autre demande")
    charger(at, ancien)
    at.button("analyser").click().run()
    identifiant = at.selectbox("choix_email").value
    at.text_area(f"edition_{identifiant}").set_value("Travail humain à conserver").run()
    charger(at, nouveau)
    assert at.dataframe[0].value["État"].tolist() == ["À analyser"]
    assert at.selectbox("choix_email").value != identifiant
    assert len(client.appels) == 2
    at.button("analyser").click().run()
    assert not at.exception and len(client.appels) == 4
    charger(at, ancien)
    assert at.text_area(f"edition_{identifiant}").value == "Travail humain à conserver"
    assert len(client.appels) == 4


def test_erreurs_isolees_et_autres_resultats_consultables(monkeypatch):
    client, _ = simulation(monkeypatch, ConnectionError("indisponible"), analyse(), BROUILLON_AUTORISE)
    at = ouvrir()
    fichiers = [
        ("illisible.txt", b"\xff\xfe\xfa", "text/plain"), fichier("vide.txt", " \n"),
        fichier("connexion.txt"), fichier("valide.txt"),
    ]
    charger(at, *fichiers)
    assert at.metric[2].value == "1"
    at.button("analyser").click().run()
    assert not at.exception
    assert len(client.appels) == 3
    assert at.dataframe[0].value["État"].tolist() == ["Erreur", "Erreur", "Erreur", "Traité"]
    assert at.metric[1].value == "1" and at.metric[2].value == "3"
    for nom, contenu, _ in fichiers[:3]:
        identifiant = identifiant_email(nom, contenu)
        at.selectbox("choix_email").select(identifiant).run()
        assert not at.exception and at.error
        assert any("Erreur technique" in c.value for c in at.caption)
    valide = identifiant_email(fichiers[3][0], fichiers[3][1])
    at.selectbox("choix_email").select(valide).run()
    assert at.text_area(f"edition_{valide}").value
    assert not at.error and len(client.appels) == 3


def test_echec_brouillon_analyse_preservee_et_reessai_cible(monkeypatch):
    client, _ = simulation(
        monkeypatch, analyse(), BROUILLON_AUTORISE, analyse(), "invalide", "invalide",
        analyse(), BROUILLON_AUTORISE,
    )
    at = ouvrir()
    charger(at, fichier("a.txt"), fichier("b.txt"))
    at.button("analyser").click().run()
    assert not at.exception and len(client.appels) == 5
    premier, second = list(at.session_state["emails"])
    at.text_area(f"edition_{premier}").set_value("Correction conservée après un nouvel essai").run()
    at.selectbox("choix_email").select(second).run()
    assert any("L’analyse a réussi" in i.value for i in at.info)
    assert at.session_state["resultats"][second]["analyse"]["categorie"] == "support"
    at.button("analyser").click().run()
    assert not at.exception and len(client.appels) == 7
    assert at.dataframe[0].value["État"].tolist() == ["Traité", "Traité"]
    at.selectbox("choix_email").select(premier).run()
    assert at.text_area(f"edition_{premier}").value == "Correction conservée après un nouvel essai"
    assert len(client.appels) == 7


def test_retrait_et_changement_source_preservent_correction(monkeypatch):
    client, _ = simulation(monkeypatch, analyse(), BROUILLON_AUTORISE)
    at = ouvrir()
    email = fichier()
    charger(at, email)
    at.button("analyser").click().run()
    identifiant = at.selectbox("choix_email").value
    at.text_area(f"edition_{identifiant}").set_value("Correction à retrouver").run()
    at.radio("source").set_value("Gmail de test").run()
    at.radio("source").set_value("Fichiers locaux").run()
    charger(at, email)
    assert at.text_area(f"edition_{identifiant}").value == "Correction à retrouver"
    at.file_uploader("fichiers").clear().run()
    assert not at.exception and not at.dataframe
    charger(at, email)
    assert at.text_area(f"edition_{identifiant}").value == "Correction à retrouver"
    assert len(client.appels) == 2


def test_revue_humaine_visible_et_spam_sans_brouillon(monkeypatch):
    client, _ = simulation(
        monkeypatch, analyse(categorie="facturation"), BROUILLON_AUTORISE,
        analyse(categorie="spam"),
    )
    at = ouvrir()
    charger(at, fichier("litige.txt", "Un écart de montant sur la facture."), fichier("spam.txt", "Offre !"))
    at.button("analyser").click().run()
    assert not at.exception and len(client.appels) == 3
    assert at.metric[3].value == "1"
    assert any("Revue humaine requise" in w.value for w in at.warning)
    assert at.dataframe[0].value["Revue humaine"].tolist() == ["Oui", "Non"]
    spam = list(at.session_state["emails"])[1]
    at.selectbox("choix_email").select(spam).run()
    assert not at.download_button
    assert any("Aucune réponse n’est nécessaire" in i.value for i in at.info)


def test_reanalyse_explicitement_avec_identite_et_correction_humaine_conservee(monkeypatch):
    premier = analyse(
        entreprise_expediteur="Nova",
        resume="Alex Martin de Nova souhaite découvrir le produit.",
        justification="Alex Martin de Nova demande une démonstration du produit.",
        categorie="demo",
    )
    nouveau = premier | {"resume": "Alex Martin de Nova souhaite une démo pour suivre ses paiements."}
    client, _ = simulation(monkeypatch, premier, BROUILLON_AUTORISE, nouveau, BROUILLON_AUTORISE)
    at = ouvrir()
    charger(at, fichier(texte="From: Alex Martin <alex@example.test>\nSubject: Démo\n\n"
                             "Je travaille chez Nova et souhaite une démo."))
    at.button("analyser").click().run()
    identifiant = at.selectbox("choix_email").value
    correction = "Réponse relue et corrigée à conserver."
    at.text_area(f"edition_{identifiant}").set_value(correction).run()
    at.button("reanalyser").click().run()
    assert not at.exception
    assert at.session_state["resultats"][identifiant]["resume"] == nouveau["resume"]
    assert nouveau["resume"] in [t.value for t in at.text]
    assert nouveau["justification"] in [t.value for t in at.text]
    assert at.text_area(f"edition_{identifiant}").value == correction
    assert len(client.appels) == 4


def test_ancienne_analyse_signalee_et_actualisee_sur_clic(monkeypatch):
    client, _ = simulation(monkeypatch, analyse(), BROUILLON_AUTORISE, analyse(), BROUILLON_AUTORISE)
    at = ouvrir()
    charger(at, fichier())
    at.button("analyser").click().run()
    identifiant = at.selectbox("choix_email").value
    ancien = dict(at.session_state["resultats"][identifiant])
    ancien["resume"] = "L'utilisateur souhaite une démo."
    ancien["justification"] = "L'email demande une démo. Cela correspond au produit."
    at.session_state["resultats"] = {identifiant: ancien}
    at.session_state["versions_resultats"] = {}
    at.run()
    assert not at.exception
    assert len(client.appels) == 2
    assert at.dataframe[0].value["État"].tolist() == ["À actualiser"]
    assert any("Analyse précédente à actualiser" in w.value for w in at.warning)
    assert not at.button("analyser").disabled
    at.button("analyser").click().run()
    assert not at.exception
    assert len(client.appels) == 4
    assert at.session_state["resultats"][identifiant]["justification"] == analyse()["justification"]
    assert at.dataframe[0].value["État"].tolist() == ["Traité"]


def test_reanalyse_actualise_le_brouillon_non_modifie(monkeypatch):
    client, _ = simulation(
        monkeypatch, analyse(), BROUILLON_AUTORISE,
        analyse(categorie="question_commerciale"), BROUILLON_AUTORISE,
    )
    at = ouvrir()
    charger(at, fichier())
    at.button("analyser").click().run()
    identifiant = at.selectbox("choix_email").value
    ancien = at.text_area(f"edition_{identifiant}").value
    at.button("reanalyser").click().run()
    assert not at.exception and len(client.appels) == 4
    nouveau = at.session_state["resultats"][identifiant]["brouillon"]
    assert nouveau != ancien
    assert at.text_area(f"edition_{identifiant}").value == nouveau


def test_echec_reanalyse_preserve_resultat_et_correction_telechargeable(monkeypatch):
    client, _ = simulation(monkeypatch, analyse(), BROUILLON_AUTORISE, ConnectionError("indisponible"))
    at = ouvrir()
    charger(at, fichier())
    at.button("analyser").click().run()
    identifiant = at.selectbox("choix_email").value
    precedent = dict(at.session_state["resultats"][identifiant])
    at.text_area(f"edition_{identifiant}").set_value("Ma correction humaine").run()
    at.button("reanalyser").click().run()
    assert not at.exception and len(client.appels) == 3
    assert at.session_state["resultats"][identifiant] == precedent
    assert any("Nouvelle analyse échouée" in e.value for e in at.error)
    assert at.text_area(f"edition_{identifiant}").value == "Ma correction humaine"
    assert len(at.download_button) == 1


@pytest.mark.parametrize("categorie,objet,ancienne,attendue", [
    ("demo", "Demande de démo", "haute", "Moyenne"),
    ("demo", "URGENT - Demande de démo", "moyenne", "Haute"),
    ("spam", "URGENT - Offre", "haute", "Basse"),
    ("autre", "URGENT - Invitation", "haute", "Basse"),
    ("candidature", "Candidature spontanée", "basse", "Moyenne"),
    ("support", "Non urgent - Export CSV", "haute", "Moyenne"),
])
def test_priorite_ancienne_corrigee_dans_tableau_et_detail_sans_appel(
    monkeypatch, categorie, objet, ancienne, attendue,
):
    client, _ = simulation(monkeypatch, analyse(categorie=categorie), BROUILLON_AUTORISE)
    at = ouvrir()
    charger(at, fichier(texte=f"Subject: {objet}\n\nUne demande."))
    at.button("analyser").click().run()
    identifiant = at.selectbox("choix_email").value
    precedent = dict(at.session_state["resultats"][identifiant])
    ancien = precedent | {"priorite": ancienne}
    at.session_state["resultats"] = {identifiant: ancien}
    if precedent["brouillon"]:
        at.text_area(f"edition_{identifiant}").set_value("Correction humaine conservée").run()
    appels_avant = len(client.appels)
    # Même avec une empreinte courante, la valeur mémorisée ne prime pas sur la règle.
    at.run()
    assert not at.exception
    assert at.dataframe[0].value["Priorité"].tolist() == [attendue]
    assert any(f"**Priorité :** {attendue}" == m.value for m in at.markdown)
    assert at.session_state["resultats"][identifiant] == precedent | {"priorite": attendue.lower()}
    assert len(client.appels) == appels_avant
    if precedent["brouillon"]:
        assert at.text_area(f"edition_{identifiant}").value == "Correction humaine conservée"


def test_priorite_analyse_partielle_corrigee_sans_relancer_brouillon(monkeypatch):
    client, _ = simulation(monkeypatch, analyse(), "invalide", "invalide")
    at = ouvrir()
    charger(at, fichier(texte="Subject: URGENT - Accès au compte\n\nUne demande d’aide."))
    at.button("analyser").click().run()
    identifiant = at.selectbox("choix_email").value
    ancien = dict(at.session_state["resultats"][identifiant])
    ancien["analyse"] = ancien["analyse"] | {"priorite": "moyenne"}
    at.session_state["resultats"] = {identifiant: ancien}
    at.run()
    assert not at.exception
    assert at.session_state["resultats"][identifiant]["statut"] == "erreur"
    assert at.session_state["resultats"][identifiant]["analyse"]["priorite"] == "haute"
    assert at.dataframe[0].value["Priorité"].tolist() == ["Haute"]
    assert any("**Priorité :** Haute" == m.value for m in at.markdown)
    assert len(client.appels) == 3


def test_rapport_erreurs_visible_et_telechargeable_sans_nouvel_appel(monkeypatch, tmp_path):
    client, _ = simulation(monkeypatch, ConnectionError("indisponible"), analyse(), BROUILLON_AUTORISE)
    at = ouvrir()
    charger(at, fichier("echec.txt"), fichier("valide.txt"))
    with patch("streamlit.download_button", wraps=st.download_button) as telecharger:
        at.button("analyser").click().run()
        appels_rapport = [a for a in telecharger.call_args_list if a.kwargs.get("key") == "telecharger_erreurs"]
    assert not at.exception and len(client.appels) == 3
    assert at.dataframe[0].value.columns[:2].tolist() == ["Fichier", "État"]
    assert any(e.label == "Détail des erreurs (1)" for e in at.expander)
    assert any("Ollama est inaccessible" in t.value for t in at.text)
    rapport = json.loads(appels_rapport[-1].kwargs["data"].decode("utf-8"))
    assert len(rapport["erreurs"]) == 1
    assert rapport["erreurs"][0]["fichier"] == "echec.txt"
    assert rapport["erreurs"][0]["code"] == "connexion"
    assert rapport["erreurs"][0]["etape"] == "analyse"
    assert "Ollama inaccessible" in rapport["erreurs"][0]["message"]
    journaux = list((tmp_path / "diagnostics").glob("*.json"))
    assert len(journaux) == 1
    journal = json.loads(journaux[0].read_text(encoding="utf-8"))
    assert journal["erreurs"] == rapport["erreurs"]
    assert journal["version_traitement"]
    assert appels_rapport[-1].kwargs["on_click"] == "ignore"
    at.download_button[0].click().run()
    assert not at.exception and len(client.appels) == 3
    charger(at, fichier("valide.txt"))
    assert not any("Détail des erreurs" in e.label for e in at.expander)
    assert len(client.appels) == 3
    assert json.loads(journaux[0].read_text(encoding="utf-8"))["erreurs"] == []


def test_rapport_distingue_echec_du_brouillon_et_sortie_modele_invalide(monkeypatch):
    client, _ = simulation(monkeypatch, analyse(), "invalide", "invalide")
    at = ouvrir()
    charger(at, fichier())
    with patch("streamlit.download_button", wraps=st.download_button) as telecharger:
        at.button("analyser").click().run()
        appels_rapport = [a for a in telecharger.call_args_list if a.kwargs.get("key") == "telecharger_erreurs"]
    assert not at.exception and len(client.appels) == 3
    rapport = json.loads(appels_rapport[-1].kwargs["data"].decode("utf-8"))
    assert rapport["erreurs"][0]["code"] == "sortie_invalide"
    assert rapport["erreurs"][0]["etape"] == "brouillon"
    assert "deux tentatives" in rapport["erreurs"][0]["cause"]
    assert "BrouillonContraint invalide" in rapport["erreurs"][0]["message"]
    assert at.session_state["resultats"][at.selectbox("choix_email").value]["analyse"] is not None


def test_reessai_erreurs_uniquement_preserve_succes_et_corrections(monkeypatch):
    client, _ = simulation(
        monkeypatch, analyse(), BROUILLON_AUTORISE, analyse(), "invalide", "invalide",
        analyse(), BROUILLON_AUTORISE,
    )
    at = ouvrir()
    charger(at, fichier("succes.txt"), fichier("echec.txt"))
    at.button("analyser").click().run()
    premier, second = list(at.session_state["emails"])
    resultat_avant = dict(at.session_state["resultats"][premier])
    at.text_area(f"edition_{premier}").set_value("Ma correction à conserver").run()
    versions = dict(at.session_state["versions_resultats"])
    versions[premier] = "ancienne_version"
    at.session_state["versions_resultats"] = versions
    at.run()
    at.button("reessayer_erreurs").click().run()
    assert not at.exception and len(client.appels) == 7
    assert at.session_state["resultats"][premier] == resultat_avant
    assert at.session_state["resultats"][second]["statut"] == "succes"
    assert at.text_area(f"edition_{premier}").value == "Ma correction à conserver"
    at.run()
    assert at.button("reessayer_erreurs").disabled


def test_echec_journal_local_ne_bloque_pas_le_traitement(monkeypatch):
    def journal_indisponible(*args):
        raise PermissionError("Dossier inaccessible")

    monkeypatch.setattr("diagnostics.enregistrer_rapport", journal_indisponible)
    client, _ = simulation(monkeypatch, analyse(), BROUILLON_AUTORISE)
    at = ouvrir()
    charger(at, fichier())
    at.button("analyser").click().run()
    assert not at.exception and len(client.appels) == 2
    assert any("rapport local n’a pas pu être enregistré" in w.value for w in at.warning)
    assert at.session_state["resultats"][at.selectbox("choix_email").value]["statut"] == "succes"
