# Journal de vérification

Ce document sépare observations effectuées, contrôles simulés et validations
restantes. Les métriques de classification ne sont jamais déduites des tests.

## Inspection initiale

- Sujet : trois pages lues par extraction `pypdf`, copie dans `sujet_extrait.txt`.
  L'extraction de certains glyphes accentués du PDF est imparfaite ; les emails
  originaux, eux, sont intégralement lisibles en UTF-8.
- Vingt emails, sans pièce jointe réelle, 13 FR / 7 EN. Empreintes initiales dans
  `entrees_sha256.json` ; les fichiers d'entrée ne sont jamais réécrits par le code.
- Aucun code préexistant ni instruction `AGENTS.md` trouvée dans le dépôt ou aux
  emplacements parents contrôlés. Dépôt initial sans commit, identité Git
  préconfigurée conservée.
- Python 3.14.0 ; Ollama 0.40.16. `ollama list` était vide avant le téléchargement.
- Matériel relevé par les commandes Windows CIM : Ryzen 5 4600H, 6 cœurs / 12
  threads, RAM 16 505 847 808 octets, GTX 1650 Ti de 4 Go.
- `nvidia-smi` : 4096 MiB de VRAM, 3274 MiB libres lors du relevé, pilote 457.49.
  La mémoire libre est une photographie ponctuelle, pas une garantie d'exécution
  GPU. Un pilote ancien peut limiter l'accélération ; seul l'essai réel le tranche.

## Tests simulés

Première passe : 21 réussites et 2 échecs. Les deux échecs concernaient la même
cause : appel de `confusion_matrix` sans aucun exemple réussi. Correction :
matrice 8×8 nulle et scores non calculables lorsque la couverture est nulle.

Après correction : 23 tests réussis. Trois tests supplémentaires ont ensuite été
ajoutés pour le code de retour d'un lot partiel, le retrait d'un ancien brouillon
après échec et la protection d'un fichier non géré. Nouvelle passe : **26 tests
réussis** avec le Python système. Analyse statique `ruff check` : aucun problème
après corrections.

Installation isolée : `.venv` créé avec Python 3.14 ; installation effective de
`requirements.txt` terminée. `pip check` : aucune dépendance cassée. Les versions
installées correspondent exactement aux versions directes et transitives figées.
Tests dans ce venv : **26 réussis en 13,13 secondes**. Ces mesures concernent les
tests simulés et ne constituent pas une mesure de latence du modèle.

Tous les messages des tests sont synthétiques et les réponses Ollama simulées.
La présence d'une injection dans un message utilisateur est vérifiée comme
frontière structurelle ; cela ne certifie pas le comportement sémantique du modèle.

## Construction des prompts et séparation des données

Version initiale : lecture des 20 emails et du sujet pour expliciter les règles.
Cas qui ont informé les consignes : `01/02/16` (démo et agenda), `03/04` (faits
produit absents), `05/07/18/19` (sensibilité), `08` (action non réalisée),
`10` (partenariat plutôt qu'intégration avant-vente), `11/12` (pièces jointes non
accessibles), `15/20` (autre avec/sans réponse), `17` (procédure support inconnue).
Ce sont des exemples de développement ; aucun jeu d'évaluation indépendant
n'est revendiqué. Pas d'exemple de réponse de référence fourni au modèle.

Les annotations ont été proposées séparément avant les prédictions, avec un
commentaire par email. Elles ne sont pas chargées par `main.py`. Leur statut
reste **à valider par Bochra** ; elles ne sont pas un étiquetage humain validé.

## Exécution réelle

Premier contrôle pendant le téléchargement : exécution sur une copie de
`email_01.txt`, modèle encore absent. Résultat observé : 0 réussite, 1 échec,
`type_erreur="modele_indisponible"`, erreur Ollama HTTP 404 enregistrée dans le
JSON. Ce contrôle vérifie le chemin d'erreur, pas une inférence réussie.
Le contrôle a ensuite été reproduit dans le venv : code de retour Python **1**,
bilan 0 réussite / 1 échec, conformément au contrat du CLI.

Relecture de code avant inférence : le signal lexical `avoir` isolé était trop
large pour « avoir des renseignements ». Il est restreint à `un avoir` / `cet avoir`.
Un test synthétique de non-régression couvre cette phrase. Les négations et
citations restent des limites du filet lexical conservateur.
Après cette correction : **27 tests réussis en 3,98 secondes dans le venv** ;
analyse statique sans problème. Le code de traitement n'a pas été ajusté à des
prédictions du modèle à ce stade.

Le téléchargement du candidat exact demandé est terminé. Premier appel structuré
réel réussi sur une demande de démo synthétique : catégorie `demo`, priorité haute,
langue française, réponse nécessaire, aucune revue sensible. Détails complets dans
`diagnostic_modele.json` : digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`,
4.0B, GGUF `Q4_K_M`, 2 497 293 803 octets de poids/manifestes.

L'appel Ollama a pris **56,209 s**, dont environ **15,307 s de chargement** et
**19,901 s de génération de 122 tokens**, soit environ **6,13 tokens/s** pour la
génération seule. Le serveur indique `100% CPU`, `size_vram=0`, contexte 4096 et
environ 3,186 Go alloués au modèle chargé. Aucune accélération GPU n'est revendiquée.
Le modèle demandé reste utilisable sur CPU ; il est conservé, avec une latence
plus élevée qu'une exécution GPU. Les résultats du lot complet et de sa revue
seront inscrits ci-dessous après exécution.

### Premier lot complet et corrections

Premier lot : **20 succès techniques, 0 échec, 36 appels, 956,516 s**. Exactitude
et macro F1 **0,95** sur la référence proposée. L'appel d'offres `18` était classé
partenariat ; quatre priorités différaient et l'invitation `15` n'avait pas de réponse.
Les quatre cas sensibles étaient signalés sans faux positif ni faux négatif.

La revue des 16 brouillons par Codex a rejeté ce premier lot : conformité RGPD
affirmée, menus produit inventés, absence de programme/poste tenue pour vraie,
champs sans rapport, mauvaise langue et engagements non étayés. Les fichiers
exacts sont conservés dans `essai_initial/`, avec le prompt de cet essai.

Deuxième essai : cinq emails ciblés (`04/12/15/17/18`), rédaction libre avec
consignes raccourcies, langue explicite et champ par catégorie. RFP et invitation
étaient mieux traités, mais des affirmations non étayées persistaient sur le RGPD
et la participation à l'appel d'offres. Cet essai est aussi rejeté ; archive dans
`essai_cible/`. Il ne suffit donc pas de renforcer une consigne négative.

Correction finale de conception : `redaction.propositions_brouillons` fournit
des formulations prudentes, dans la langue de l'analyse. Le deuxième appel
choisit un texte complet ; `schema_brouillon` contraint le champ `corps` à ces
seules valeurs via une enum. Pydantic refuse tout texte libre, même JSON valide.
Ces formulations sont définies par Codex dans le code et restent à faire valider
par Bochra ; aucune approbation métier FAKTUS n'est revendiquée.

Troisième contrôle ciblé sur les cinq mêmes emails : cinq succès, textes relus
par Codex, aucune affirmation de conformité, participation ou procédure inventée.
La priorité commerciale non sensible encore trop haute dans ce contrôle a
motivé la mise en Python de toute la politique de priorité. La classification et
la décision de réponse restent des décisions sémantiques du modèle, sauf spam.

Résumé : contrôle d'une phrase par ponctuation et retour explicite de la cause
en cas de validation invalide. Une abréviation peut être prise à tort pour une
fin de phrase. Tests après ces changements : **32 réussis** ; analyse statique
sans problème. Une nouvelle exécution complète a été effectuée avec ce code.

Les scores comparent l'application après règles à la référence, pas les priorités
brutes du modèle. Aucun changement des annotations n'a été fait pour améliorer
le résultat. Tous les exemples ci-dessus font désormais partie du développement.

### Lot final réellement exécuté

- Commande : `.venv\Scripts\python main.py --input emails --output outputs`.
- Code de retour **0**, **20 réussites, 0 échec**, **17 brouillons**.
- **1 007,722 s** (16 min 47,722 s) sur CPU, **39 appels** et **4 307 tokens générés**.
- 22 appels d'analyse : deux reprises de validation sur `06` et `16`, réussies
  au second essai ; 17 choix de brouillons contraints.
- Évaluation réelle : code **0**, couverture **1,00**, exactitude **1,00**, macro
  F1 **1,00** sur la référence proposée ; aucun écart sur langue, priorité,
  besoin de réponse et revue humaine. Quatre cas sensibles retrouvés, zéro faux
  négatif, zéro faux positif, zéro non-évalué.
- Ces scores mesurent l'application après règles, sur le corpus de développement
  dont les annotations restent à valider. Ils ne mesurent pas la fidélité de la
  prose des résumés/justifications, ni des emails nouveaux.
- Vérification des artefacts : 20 noms uniques correspondant aux entrées,
  schémas validés, 17 textes identiques entre JSON et fichiers, tous présents
  dans le catalogue autorisé, empreintes du manifeste exactes, empreintes des
  prompts/catalogue correspondant au code exécuté. Les 20 sources ont conservé
  leur empreinte initiale. Aucun fichier de réponse pour `13/14/20`.
- La relance réelle a remplacé les 16 anciens brouillons et ajouté celui de `15`.
  Les cas de suppression d'un ancien brouillon et de protection d'une retouche
  humaine sont vérifiés séparément par les tests simulés.
- Vérifications finales : **32 tests réussis en 4,33 s** dans le venv ; `pip check`
  sans conflit ; `ruff check` et `git diff --check` sans problème.

### Deux contrôles réels hors corpus

Les attentes figurent dans `tests/cas_synthetiques.json`, créé avant ces appels.
Les observations intégrales sont dans `robustesse_reelle.json`, séparées des scores
sur les 20 emails fournis.

1. Vente de contacts contenant une instruction de se classer en démo : `spam`,
   français, aucune réponse. Attentes respectées. Un seul exemple ne prouve pas
   une résistance générale aux injections.
2. Salutation « Bonjour / Hello », demande principale anglaise : `demo` correct,
   mais langue `fr` au lieu de `en`, donc brouillon français. **Échec de langue**
   conservé comme limite connue. La consigne du prompt sur le bilinguisme ne
   suffit pas sur cet exemple. Aucune réussite bilingue générale n'est revendiquée.

La revue de prose est consignée dans `revue_assistant.md`, distincte de la grille
de validation humaine. Les brouillons fermés sont prudents mais moins personnalisés.

## Validation restante

- Validation des annotations et des choix de priorité par Bochra.
- Relecture des brouillons et remplissage de la grille `grille_revue.md`.
- Compléter les champs manquants avec des informations FAKTUS approuvées avant usage.
- Un jeu indépendant est nécessaire pour évaluer la généralisation.
