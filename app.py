"""Une page Streamlit ; le traitement métier reste dans agent.traiter_email."""

import json
import time
from collections import Counter
from email import policy
from email.parser import Parser
from pathlib import Path, PureWindowsPath
from uuid import uuid4

import streamlit as st

from agent import determiner_priorite, traiter_email
from diagnostics import enregistrer_rapport
from llm import ErreurTraitement, OllamaLLM
from main import empreinte
from schemas import Echec


CATEGORIES = {
    "demo": "Démonstration", "question_commerciale": "Question commerciale",
    "support": "Support", "facturation": "Facturation", "partenariat": "Partenariat",
    "candidature": "Candidature", "spam": "Spam", "autre": "Autre",
}
SIGNAUX = {
    "incident_bloquant": "Incident bloquant", "litige_facturation": "Litige de facturation",
    "appel_offres": "Appel d’offres",
}
CAUSES_ERREURS = {
    "sortie_invalide": "Le modèle n'a pas respecté le format demandé après deux tentatives.",
    "timeout": "Le délai d'attente du modèle a été dépassé.",
    "connexion": "Ollama est inaccessible.",
    "modele_indisponible": "Le modèle demandé n'est pas disponible dans Ollama.",
    "ollama": "Ollama a renvoyé une erreur.",
    "encodage": "Le fichier n'est pas lisible en UTF-8.",
    "email_vide": "Le fichier ne contient aucun texte.",
    "email_trop_long": "L'email dépasse la longueur acceptée.",
}


def version_analyse() -> str:
    """Une modification du traitement rend les analyses conservées à actualiser."""
    fichiers = ("agent.py", "llm.py", "prompts.py", "schemas.py", "redaction.py")
    return empreinte(b"\0".join(Path(__file__).with_name(nom).read_bytes() for nom in fichiers))


def analyse_obsolete(identifiant: str, version: str) -> bool:
    resultat = st.session_state["resultats"].get(identifiant, {})
    return bool(analyse_disponible(resultat)) and (
        st.session_state["versions_resultats"].get(identifiant) != version
    )


def identifiant_email(nom: str, contenu: bytes) -> str:
    """Le nom seul ne distingue ni les homonymes ni une nouvelle version."""
    return empreinte(nom.encode("utf-8") + b"\0" + contenu)


def charger_fichiers(fichiers) -> list[str]:
    """Adapte les octets uploadés à l'entrée texte attendue par l'agent."""
    identifiants = []
    for fichier in fichiers:
        nom = PureWindowsPath(fichier.name).name
        contenu = fichier.getvalue()
        identifiant = identifiant_email(nom, contenu)
        if identifiant not in st.session_state["emails"]:
            texte = None
            try:
                # Même encodage que main.lire_email, sans fichier temporaire.
                texte = contenu.decode("utf-8-sig")
            except UnicodeError:
                st.session_state["resultats"][identifiant] = Echec(
                    fichier=nom, type_erreur="encodage",
                    message="Email illisible : UTF-8 attendu. Recharge un fichier enregistré en UTF-8.",
                ).model_dump()
            entetes = Parser(policy=policy.default).parsestr(texte or "", headersonly=True)
            st.session_state["emails"][identifiant] = {
                "nom": nom, "texte": texte,
                "objet": str(entetes.get("Subject", "")),
                "expediteur": str(entetes.get("From", "")),
            }
        # Un doublon strict (même nom et mêmes octets) représente un seul email.
        if identifiant not in identifiants:
            identifiants.append(identifiant)
    return identifiants


def analyse_disponible(resultat: dict) -> dict:
    """Un échec de rédaction peut néanmoins conserver une analyse valide."""
    return resultat if resultat.get("statut") == "succes" else resultat.get("analyse") or {}


def actualiser_priorites() -> None:
    """Appliquer aussi la règle courante aux analyses déjà conservées en session."""
    for identifiant, resultat in st.session_state["resultats"].items():
        email = st.session_state["emails"].get(identifiant, {})
        analyse = analyse_disponible(resultat)
        if analyse and email.get("texte") is not None:
            analyse["priorite"] = determiner_priorite(email["texte"], analyse["categorie"])


def afficher_erreurs(identifiants: list[str], noms: dict[str, str], version: str) -> None:
    erreurs = []
    for identifiant in identifiants:
        resultat = st.session_state["resultats"].get(identifiant, {})
        if resultat.get("statut") != "erreur":
            continue
        code = resultat["type_erreur"]
        if resultat.get("analyse"):
            etape = "brouillon"
        elif code in {"encodage", "email_vide", "email_trop_long"}:
            etape = "lecture"
        else:
            etape = "analyse"
        erreurs.append({
            "fichier": noms[identifiant], "code": code, "etape": etape,
            "cause": CAUSES_ERREURS.get(code, "Le traitement a échoué."),
            "message": resultat["message"],
        })
    try:
        enregistrer_rapport(st.session_state["session_diagnostic"], erreurs, version)
    except OSError:
        st.warning("Le rapport local n’a pas pu être enregistré. Le téléchargement reste disponible.")
    if erreurs:
        with st.expander(f"Détail des erreurs ({len(erreurs)})"):
            for erreur in erreurs:
                st.write(f"**{erreur['fichier']}** — {erreur['etape']}")
                st.text(f"{erreur['cause']}\n{erreur['message']}")
            st.download_button(
                "Télécharger le rapport d’erreurs",
                data=json.dumps({"erreurs": erreurs}, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name="rapport_erreurs.json", mime="application/json", on_click="ignore",
                key="telecharger_erreurs",
            )


def afficher_liste(zone, identifiants: list[str], noms: dict[str, str], version: str) -> None:
    resultats = st.session_state["resultats"]
    lignes = []
    for identifiant in identifiants:
        resultat = resultats.get(identifiant, {})
        analyse = analyse_disponible(resultat)
        if resultat.get("statut") == "erreur":
            etat = "Erreur"
        elif analyse_obsolete(identifiant, version):
            etat = "À actualiser"
        elif resultat.get("statut") == "succes":
            etat = "Traité"
        else:
            etat = "À analyser"
        revue = "—"
        if analyse:
            revue = "Oui" if analyse["a_valider_par_humain"] else "Non"
        lignes.append({
            "Fichier": noms[identifiant],
            "État": etat,
            "Objet": st.session_state["emails"][identifiant]["objet"] or "—",
            "Catégorie": CATEGORIES.get(analyse.get("categorie"), "—"),
            "Priorité": analyse.get("priorite", "—").capitalize(),
            "Revue humaine": revue,
        })
    with zone.container():
        compteurs = st.columns(4)
        valeurs = [
            ("Emails chargés", len(identifiants)),
            ("Traités", sum(resultats.get(i, {}).get("statut") == "succes" for i in identifiants)),
            ("En erreur", sum(resultats.get(i, {}).get("statut") == "erreur" for i in identifiants)),
            ("À relire", sum(bool(analyse_disponible(resultats.get(i, {})).get("a_valider_par_humain"))
                             for i in identifiants)),
        ]
        for colonne, (libelle, nombre) in zip(compteurs, valeurs):
            colonne.metric(libelle, nombre)
        st.subheader("Emails chargés")
        st.dataframe(lignes, hide_index=True, width="stretch")


def analyser_emails(identifiants: list[str], noms: dict[str, str], version: str) -> None:
    """Un client par clic, une erreur métier/technique isolée par email."""
    llm = OllamaLLM()
    progression = st.progress(0, text=f"0 / {len(identifiants)} email terminé")
    with st.status("Analyse en cours…", expanded=True) as suivi:
        st.caption("Le chargement du modèle et les appels sur CPU peuvent prendre plusieurs minutes. "
                   "La progression avance à la fin de chaque email.")
        echecs = 0
        for position, identifiant in enumerate(identifiants, start=1):
            email = st.session_state["emails"][identifiant]
            precedent = st.session_state["resultats"].get(identifiant, {})
            erreur = False
            debut = time.perf_counter()
            with st.spinner(f"{position} / {len(identifiants)} — {noms[identifiant]} : "
                            "analyse et éventuel brouillon…", show_time=True):
                try:
                    resultat = traiter_email(email["texte"], email["nom"], llm)
                    st.session_state["resultats"][identifiant] = resultat.model_dump()
                    st.session_state["versions_resultats"][identifiant] = version
                    # Actualiser le brouillon intact, conserver toute modification humaine.
                    if st.session_state["corrections"].get(identifiant) == precedent.get("brouillon"):
                        st.session_state["corrections"].pop(identifiant, None)
                        st.session_state.pop(f"edition_{identifiant}", None)
                except ErreurTraitement as exc:
                    erreur = True
                    if precedent.get("statut") == "succes":
                        st.error(f"Nouvelle analyse échouée : {exc}. "
                                 "L’analyse précédente et tes corrections sont conservées.")
                    else:
                        st.session_state["resultats"][identifiant] = Echec(
                            fichier=email["nom"], type_erreur=exc.code,
                            message=str(exc), analyse=exc.analyse,
                        ).model_dump()
                        st.session_state["versions_resultats"][identifiant] = version
                        st.error(f"{noms[identifiant]} : {exc}")
                    echecs += 1
            st.text(f"{noms[identifiant]} : {'erreur' if erreur else 'traité'} "
                    f"({time.perf_counter() - debut:.1f} s)")
            progression.progress(position / len(identifiants),
                                 text=f"{position} / {len(identifiants)} email(s) terminé(s)")
        suivi.update(label=f"Analyse terminée : {len(identifiants) - echecs} traité(s), "
                           f"{echecs} erreur(s).", state="error" if echecs else "complete", expanded=True)


def memoriser_correction(identifiant: str, cle_widget: str) -> None:
    # Le widget peut disparaître lors d'une sélection ; ce dictionnaire reste.
    st.session_state["corrections"][identifiant] = st.session_state[cle_widget]


def afficher_detail(identifiant: str, version: str) -> None:
    email = st.session_state["emails"][identifiant]
    resultat = st.session_state["resultats"].get(identifiant, {})
    analyse = analyse_disponible(resultat)
    gauche, droite = st.columns(2, gap="large")
    with gauche, st.container(border=True):
        st.subheader("Email original")
        st.text(f"Objet : {email['objet'] or 'Non renseigné'}")
        st.text(f"Expéditeur : {email['expediteur'] or 'Non renseigné'}")
        if email["texte"] is None:
            st.warning("Le contenu ne peut pas être affiché : le fichier n’est pas lisible en UTF-8.")
        else:
            st.text_area("Contenu original", value=email["texte"], height=300,
                         disabled=True, key=f"original_{identifiant}")
    with droite, st.container(border=True):
        st.subheader("Analyse")
        if analyse_obsolete(identifiant, version):
            st.warning("Analyse précédente à actualiser. Clique sur « Réanalyser cet email » "
                       "pour appliquer les consignes actuelles de résumé et de justification.")
        if resultat.get("statut") == "erreur":
            st.error(f"Traitement échoué : {resultat['message']}")
            st.caption(f"Erreur technique : {resultat['type_erreur']}. Ce n’est pas une catégorie d’email.")
            if analyse:
                st.info("L’analyse a réussi, mais le brouillon n’a pas pu être produit.")
        elif not resultat:
            st.info("Cet email est à analyser. Utilise le bouton dans la barre latérale.")
        if analyse:
            if analyse["a_valider_par_humain"]:
                st.warning("Revue humaine requise avant toute utilisation du brouillon.")
            st.write("**Catégorie :**", CATEGORIES[analyse["categorie"]])
            st.write("**Priorité :**", analyse["priorite"].capitalize())
            st.caption({
                "haute": "Une urgence explicite est indiquée dans l’objet.",
                "moyenne": "Aucune urgence explicite n’est retenue dans l’objet.",
                "basse": "Les catégories Spam et Autre sont toujours en priorité basse.",
            }[analyse["priorite"]])
            st.write("**Langue :**", {"fr": "Français", "en": "Anglais"}[analyse["langue"]])
            st.write("**Résumé**")
            st.text(analyse["resume"])
            st.write("**Justification**")
            st.text(analyse["justification"])
            st.write("**Réponse nécessaire :**", "Oui" if analyse["reponse_necessaire"] else "Non")
            st.write("**Signaux sensibles :**",
                     ", ".join(SIGNAUX[s] for s in analyse["cas_sensibles"]) or "Aucun détecté")
            st.write("**Revue humaine :**", "Requise" if analyse["a_valider_par_humain"] else "Non requise")

    st.subheader("Brouillon de réponse")
    if not analyse:
        st.info("Aucun brouillon disponible pour cet email.")
    elif not analyse["reponse_necessaire"]:
        st.info("Aucune réponse n’est nécessaire pour cet email.")
    elif resultat.get("statut") != "succes":
        st.info("Le brouillon n’est pas disponible. Tu peux réessayer l’analyse depuis la barre latérale.")
    else:
        initial = resultat["brouillon"]
        st.session_state["corrections"].setdefault(identifiant, initial)
        cle = f"edition_{identifiant}"
        if cle not in st.session_state:
            st.session_state[cle] = st.session_state["corrections"][identifiant]
        st.caption("Modifie librement le texte et complète les informations manquantes. "
                   "Les corrections sont conservées pendant cette session.")
        texte = st.text_area("Texte corrigé", height=240, key=cle,
                             on_change=memoriser_correction, args=(identifiant, cle))
        with st.expander("Voir le brouillon initial généré"):
            st.text(initial)
        st.download_button(
            "Télécharger le texte corrigé", data=texte.encode("utf-8"),
            file_name=f"{PureWindowsPath(email['nom']).stem}_{identifiant[:8]}_corrige.txt",
            mime="text/plain; charset=utf-8", on_click="ignore", key=f"telecharger_{identifiant}",
        )
        st.caption("Le téléchargement ne modifie aucun fichier du projet. "
                   "Télécharge tes corrections avant de fermer ou d’actualiser la page.")


def main() -> None:
    st.set_page_config(page_title="FAKTUS · Tri des emails", page_icon="✉️", layout="wide")
    for cle in ("emails", "resultats", "corrections", "versions_resultats"):
        st.session_state.setdefault(cle, {})
    if "session_diagnostic" not in st.session_state:
        st.session_state["session_diagnostic"] = uuid4().hex
    # Calculer l'empreinte une fois par interaction, pas pour chaque ligne affichée.
    version = version_analyse()
    actualiser_priorites()
    st.title("FAKTUS · Tri des emails")
    st.caption("Analyse locale, priorisation et brouillons à relire. Aucun email n’est envoyé.")
    reessayer = False
    a_reessayer = []

    with st.sidebar:
        st.header("Sources")
        source = st.radio("Source des emails", ["Fichiers locaux", "Gmail de test"], key="source")
        fichiers = st.file_uploader(
            "Charger des emails .txt", type=["txt"], accept_multiple_files=True,
            max_upload_size=1, key="fichiers", disabled=source != "Fichiers locaux",
            help="Fichiers UTF-8, avec ou sans BOM. Le traitement refuse plus de 16 000 caractères.",
        )
        if source == "Gmail de test":
            st.warning("Connexion Gmail non configurée")
            st.button("Connecter Gmail", disabled=True)
            st.button("Appliquer un libellé", disabled=True)
            st.button("Créer ou mettre à jour un brouillon Gmail", disabled=True)
            st.info("Aucun connecteur Gmail n’est présent dans ce projet.")
            st.button("Analyser les emails", disabled=True, key="analyser_gmail")
            identifiants = []
            lancer = False
        else:
            identifiants = charger_fichiers(fichiers)
            a_traiter = []
            for identifiant in identifiants:
                resultat = st.session_state["resultats"].get(identifiant, {})
                erreur = resultat.get("statut") == "erreur"
                if identifiant not in st.session_state["resultats"] or (
                    erreur and resultat["type_erreur"] != "encodage"
                ) or analyse_obsolete(identifiant, version):
                    a_traiter.append(identifiant)
                if erreur and resultat["type_erreur"] in {
                    "sortie_invalide", "timeout", "connexion", "modele_indisponible", "ollama",
                }:
                    a_reessayer.append(identifiant)
            lancer = st.button("Analyser les emails", type="primary", width="stretch",
                               disabled=not a_traiter, key="analyser")
            reessayer = st.button("Réessayer les erreurs", disabled=not a_reessayer,
                                  key="reessayer_erreurs")
            st.caption("Seuls les emails à analyser, à actualiser ou en erreur sont traités. "
                       "Les corrections humaines du brouillon sont conservées.")
            st.caption("Un fichier retiré peut être rechargé à l’identique pour retrouver "
                       "ses corrections pendant cette session.")

    if source == "Gmail de test":
        st.info("Connexion Gmail non configurée. Choisis « Fichiers locaux » pour analyser des emails.")
        return
    if not identifiants:
        st.info("Charge un ou plusieurs fichiers .txt dans la barre latérale, puis lance l’analyse.")
        return

    frequences = Counter(st.session_state["emails"][i]["nom"] for i in identifiants)
    noms = {i: st.session_state["emails"][i]["nom"] + (
        f" · version {i[:6]}" if frequences[st.session_state["emails"][i]["nom"]] > 1 else ""
    ) for i in identifiants}
    zone_erreurs = st.empty()
    zone_liste = st.empty()
    afficher_liste(zone_liste, identifiants, noms, version)
    if st.session_state.get("choix_email") not in identifiants:
        precedent = st.session_state.get("selection")
        st.session_state["choix_email"] = precedent if precedent in identifiants else identifiants[0]
    selection = st.selectbox("Email à consulter", identifiants, format_func=noms.get, key="choix_email")
    st.session_state["selection"] = selection
    if reessayer:
        a_traiter = a_reessayer
    if lancer or reessayer:
        analyser_emails(a_traiter, noms, version)
        afficher_liste(zone_liste, identifiants, noms, version)
    reanalyser = st.button("Réanalyser cet email", key="reanalyser",
                          disabled=not st.session_state["resultats"].get(selection)
                          or st.session_state["emails"][selection]["texte"] is None,
                          help="Recalcule l’analyse et le brouillon ; conserve tes corrections humaines.")
    if reanalyser:
        analyser_emails([selection], noms, version)
        afficher_liste(zone_liste, identifiants, noms, version)
    with zone_erreurs.container():
        afficher_erreurs(identifiants, noms, version)
    afficher_detail(selection, version)


if __name__ == "__main__":
    main()
