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
après corrections. Le relevé final dans le venv sera ajouté ci-dessous.

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

Le téléchargement du candidat exact demandé a été lancé. Les résultats du
premier appel, du lot complet et de sa revue seront inscrits ici après exécution.
Aucun score réel ni qualité linguistique n'est annoncé à ce stade du journal.

## Validation restante

- Validation des annotations et des choix de priorité par Bochra.
- Relecture des brouillons et remplissage de la grille `grille_revue.md`.
- Compléter les champs manquants avec des informations FAKTUS approuvées avant usage.
- Un jeu indépendant est nécessaire pour évaluer la généralisation.
