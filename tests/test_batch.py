import json

import pytest

from main import enregistrer_sorties, main, traiter_lot
from tests.test_agent import analyse, faux_llm


def test_erreur_isolee_et_encodage(tmp_path):
    (tmp_path / "01_vide.txt").write_text("", encoding="utf-8")
    (tmp_path / "02_invalide.txt").write_bytes(b"\xff\xfe\xfa")
    (tmp_path / "03_valide.txt").write_text("Offre !", encoding="utf-8")
    llm, _ = faux_llm(analyse(categorie="spam"))
    resultats = traiter_lot(list(tmp_path.glob("*.txt")), llm)
    assert [r["statut"] for r in resultats] == ["erreur", "erreur", "succes"]
    assert [r.get("type_erreur") for r in resultats[:2]] == ["email_vide", "encodage"]


def test_relance_supprime_seulement_ancien_brouillon(tmp_path):
    llm, _ = faux_llm(analyse(), {"corps": "Bonjour, à compléter."})
    path = tmp_path / "email.txt"
    path.write_text("Question", encoding="utf-8")
    resultats = traiter_lot([path], llm)
    sortie = tmp_path / "sorties"
    enregistrer_sorties(sortie, resultats, {})
    manuel = sortie / "reponses" / "notes.txt"
    manuel.write_text("Travail humain", encoding="utf-8")
    llm, _ = faux_llm(analyse(categorie="spam"))
    enregistrer_sorties(sortie, traiter_lot([path], llm), {})
    assert not (sortie / "reponses" / "email_reponse.txt").exists()
    assert manuel.exists()
    assert json.loads((sortie / "manifest.json").read_text()) == {}
    assert json.loads((sortie / "resultats.json").read_text())[0]["brouillon"] is None


def test_brouillon_humain_protege(tmp_path):
    llm, _ = faux_llm(analyse(), {"corps": "Brouillon initial"})
    path = tmp_path / "email.txt"
    path.write_text("Question", encoding="utf-8")
    resultats = traiter_lot([path], llm)
    sortie = tmp_path / "sorties"
    enregistrer_sorties(sortie, resultats, {})
    brouillon = sortie / "reponses" / "email_reponse.txt"
    brouillon.write_text("Correction humaine", encoding="utf-8")
    with pytest.raises(ValueError, match="modifié"):
        enregistrer_sorties(sortie, [], {})
    assert brouillon.read_text(encoding="utf-8") == "Correction humaine"


def test_manifeste_chemin_exterieur_refuse(tmp_path):
    (tmp_path / "manifest.json").write_text('{"../secret_reponse.txt":"abc"}')
    with pytest.raises(ValueError, match="Chemin interdit"):
        enregistrer_sorties(tmp_path, [], {})


def test_entree_absente_ou_vide(tmp_path):
    assert main(["--input", str(tmp_path / "absent"), "--output", str(tmp_path / "out")]) == 2
    assert main(["--input", str(tmp_path), "--output", str(tmp_path / "out")]) == 2


def test_cli_echec_partiel_code_un(tmp_path, monkeypatch):
    entree = tmp_path / "entree"
    entree.mkdir()
    (entree / "01.txt").write_text("", encoding="utf-8")
    (entree / "02.txt").write_text("Offre", encoding="utf-8")
    llm, _ = faux_llm(analyse(categorie="spam"))
    monkeypatch.setattr("main.OllamaLLM", lambda *args: llm)
    sortie = tmp_path / "out"
    assert main(["--input", str(entree), "--output", str(sortie)]) == 1
    resultats = json.loads((sortie / "resultats.json").read_text(encoding="utf-8"))
    assert [r["statut"] for r in resultats] == ["erreur", "succes"]


def test_relance_echec_retire_ancien_brouillon(tmp_path):
    llm, _ = faux_llm(analyse(), {"corps": "À vérifier"})
    path = tmp_path / "email.txt"
    path.write_text("Question", encoding="utf-8")
    sortie = tmp_path / "out"
    enregistrer_sorties(sortie, traiter_lot([path], llm), {})
    path.write_text("", encoding="utf-8")
    enregistrer_sorties(sortie, traiter_lot([path], llm), {})
    assert not (sortie / "reponses" / "email_reponse.txt").exists()


def test_collision_fichier_non_gere_preservee(tmp_path):
    sortie = tmp_path / "out"
    (sortie / "reponses").mkdir(parents=True)
    manuel = sortie / "reponses" / "email_reponse.txt"
    manuel.write_text("Texte humain", encoding="utf-8")
    llm, _ = faux_llm(analyse(), {"corps": "Génération"})
    path = tmp_path / "email.txt"
    path.write_text("Question", encoding="utf-8")
    with pytest.raises(ValueError, match="non géré"):
        enregistrer_sorties(sortie, traiter_lot([path], llm), {})
    assert manuel.read_text(encoding="utf-8") == "Texte humain"
