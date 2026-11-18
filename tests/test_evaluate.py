import pytest

from evaluate import evaluer
from schemas import Echec, Resultat
from tests.test_agent import analyse


def reference():
    return {"statut": "à valider par Bochra", "origine": "annotation synthétique de test",
            "annotations": [{"fichier": "a.txt", "categorie": "support", "langue": "fr",
                             "priorite": "moyenne", "reponse_necessaire": True,
                             "a_valider_par_humain": True, "commentaire": "Test"}]}


def test_matrice_huit_categories_et_faux_negatif():
    pred = Resultat(fichier="a.txt", brouillon="Bonjour", **analyse()).model_dump()
    rapport = evaluer(reference(), [pred])
    assert rapport["exactitude"] == 1
    assert rapport["couverture"] == 1
    assert len(rapport["matrice_confusion"]) == 8
    assert all(len(ligne) == 8 for ligne in rapport["matrice_confusion"])
    assert rapport["sensibles"]["faux_negatifs"] == ["a.txt"]
    assert rapport["macro_f1"] == 0.125  # sept classes sans support, F1=0


def test_couverture_echec_et_predictions_sans_reference():
    erreur = Echec(fichier="a.txt", type_erreur="timeout", message="Test").model_dump()
    extra = Echec(fichier="extra.txt", type_erreur="timeout", message="Test").model_dump()
    rapport = evaluer(reference(), [extra, erreur])
    assert rapport["couverture"] == 0
    assert rapport["exactitude"] is None
    assert rapport["sensibles"]["non_evalues"] == ["a.txt"]
    assert rapport["predictions_sans_reference"] == ["extra.txt"]


def test_doublons_interdits():
    ref = reference()
    ref["annotations"] *= 2
    with pytest.raises(ValueError, match="Doublon"):
        evaluer(ref, [])


def test_correspondance_par_nom_pas_par_position():
    erreur = Echec(fichier="inconnu.txt", type_erreur="timeout", message="Test").model_dump()
    rapport = evaluer(reference(), [erreur])
    assert rapport["predictions_manquantes"] == ["a.txt"]
    assert rapport["nombre_evalues"] == 0
