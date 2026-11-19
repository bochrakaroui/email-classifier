# Guide de révision et préparation du débrief

Ce guide décrit le code du dépôt. Lire un fichier, exécuter un test associé puis
expliquer son comportement à voix haute est un bon rythme de révision.

## 1. Ordre de lecture conseillé

1. `README.md`, le PDF et `emails/email_01.txt` : objectif, contraintes, exemple brut.
2. `schemas.py` : les contrats qui décrivent les entrées/sorties des étapes.
3. `redaction.py`, puis `prompts.py` : formulations prudentes et consignes du modèle.
4. `llm.py` : l'appel au modèle et la validation de sa réponse.
5. `agent.py` : le parcours central d'un email et ses invariants.
6. `main.py` : le lot, les fichiers, les sorties et les codes de retour.
7. `annotations.json` puis `evaluate.py` : référence et mesure de qualité.
8. `tests/`, `docs/verification.md`, `docs/grille_revue.md` et `outputs/` : preuves,
   erreurs observées, limites et propositions à revoir.

## 2. Parcours complet d'un email

Pour `email_07.txt`, `main` trouve le fichier dans un tri stable par nom.
`lire_email` charge l'UTF-8 sans modifier le fichier d'origine. `traiter_lot`
transmet le texte et le nom à `traiter_email`.

L'agent vérifie que le texte n'est ni vide ni trop long. `messages_analyse`
construit deux messages : instructions système et données utilisateur.
`OllamaLLM.generer` demande une sortie respectant le schéma `Analyse` et la valide.
Le modèle devrait reconnaître une contestation de facture. Indépendamment de
cette prédiction, `appliquer_regles` repère « écart de montant » ou « un avoir » et
impose la revue humaine et la priorité haute. Cette détection lexicale ne réécrit
pas la catégorie prédite : une mauvaise catégorie reste donc mesurable.

Si la réponse est pertinente, `propositions_brouillons` construit des réponses
prudentes dans la langue de l'analyse. `schema_brouillon` limite le champ `corps`
à ces textes exacts. `messages_brouillon` joint l'email, l'analyse validée et les
propositions ; le même modèle en choisit une et la renvoie intégralement.
Pour le litige, la formulation demande une vérification sans confirmer de montant,
avoir ou remboursement. Aucun texte libre n'est admis dans cette étape.

`Resultat` ajoute le nom du fichier depuis Python et contrôle la cohérence.
`enregistrer_sorties` écrit la ligne dans le JSON et le brouillon dans son fichier.
Si le second appel échoue, l'erreur conserve l'analyse mais aucun brouillon courant
n'est publié pour cet email. Le lot continue avec le suivant.

## 3. Fonctions et objets importants

| Élément | Entrées | Sortie et responsabilité |
|---|---|---|
| `schemas.Analyse` | JSON du premier appel | Catégorie, priorité, langue, résumé, justification, besoin de réponse/revue et signaux typés. |
| `schemas.Analyse.verifier_phrase_unique` | Résumé | Refuse une seconde phrase détectée par ponctuation ou un saut de ligne. |
| `schemas.Brouillon` | JSON du second appel | Texte non vide, de longueur bornée. |
| `schemas.schema_brouillon` | Liste de textes autorisés | Classe Pydantic temporaire dont le champ `corps` est une enum de ces textes exacts. |
| `redaction.propositions_brouillons` | Analyse validée | Réponses prudentes en FR/EN, adaptées aux signaux sensibles et à la catégorie. |
| `schemas.Resultat.verifier_coherence` | Résultat à construire | Refuse spam avec réponse, contradiction réponse/brouillon et signal sensible sans revue. |
| `schemas.Echec` | Nom, code et message ; analyse facultative | Représentation distincte d'une erreur technique. |
| `schemas.Annotation` | Ligne de référence | Attend les six décisions métier et un commentaire. |
| `prompts.messages_analyse` | Texte de l'email | Liste de messages destinée au premier appel. |
| `prompts.messages_brouillon` | Email et `Analyse` validée | Liste de messages destinée au second appel. |
| `llm.OllamaLLM.__init__` | Modèle, hôte, timeout, client facultatif | Configure le client officiel ; injection d'un faux client dans les tests. |
| `llm.OllamaLLM.generer` | Messages et classe de schéma | Objet Pydantic validé ou `ErreurTraitement` ; au plus deux tentatives si sortie invalide. |
| `llm.ErreurTraitement` | Code et message | Exception métier technique ; porte l'analyse si la rédaction échoue. |
| `agent.detecter_signaux` | Email | Liste de signaux sensibles trouvés par expressions régulières. |
| `agent.appliquer_regles` | Email et analyse du modèle | Nouvelle analyse avec invariants Python appliqués et revalidés. |
| `agent.traiter_email` | Texte, nom du fichier, objet LLM | Résultat complet ou exception ; orchestre les deux étapes. |
| `main.lire_email` | Chemin | Texte UTF-8/BOM, ou erreur lisible. |
| `main.traiter_lot` | Liste de chemins et LLM | Liste stable de succès et d'erreurs ; poursuit après un échec attendu. |
| `main.empreinte` / `empreinte_fichier` | Octets / chemin | SHA-256 ; `None` si le fichier ne peut pas être lu lors du relevé. |
| `main.ecrire_texte` / `ecrire_json` | Chemin et contenu | Écrit puis remplace atomiquement un fichier via un temporaire unique. |
| `main.enregistrer_sorties` | Dossier, résultats, métadonnées | Préserve les fichiers humains, écrit les sorties et retire les brouillons périmés possédés. |
| `main.main` | Arguments CLI | Exécute le lot, rassemble les mesures, renvoie 0, 1 ou 2. |
| `evaluate.indexer` | Lignes et schéma facultatif | Dictionnaire par nom ; refuse les doublons et les lignes invalides. |
| `evaluate.evaluer` | Référence et résultats | Rapport : couverture, scores, erreurs métier et cas sensibles. |
| `evaluate.main` | Arguments CLI | Lit les données, enregistre et affiche le rapport, renvoie son code. |

Une empreinte SHA-256 est un condensé du contenu : un changement d'octets change
en pratique son empreinte. Elle permet ici de repérer une retouche humaine, sans
prétendre authentifier la personne qui l'a faite.

## 4. Construction des prompts

Le prompt système dit **comment travailler** ; le message utilisateur fournit
**quoi analyser**. `json.dumps` transforme l'email en valeur JSON : guillemets,
sauts de ligne et faux marqueurs de rôle restent dans une chaîne de données.
Le modèle peut néanmoins mal interpréter une injection : la séparation de rôles
et les règles sont des protections, pas une preuve d'immunité.

`ANALYSE_SYSTEM` définit les huit catégories, les arbitrages, la priorité, la langue
et les signaux sensibles. Il demande un résumé français en une phrase et une
justification courte, pas une longue explication interne.

`messages_brouillon` demande de choisir et recopier exactement l'un des textes
autorisés. Les textes viennent de `redaction.py`, pas de l'expéditeur. Le schéma
impose la même liste : ce contrôle ne dépend donc pas du respect d'une simple
interdiction dans le prompt. Les textes n'affirment ni fonctionnalité, ni rendez-vous,
ni remboursement, ni participation à un appel d'offres. Les données manquantes
restent en champs entre crochets, à compléter avec une source approuvée.

`generer` ajoute le schéma au système pour rappeler la structure exacte au modèle.
La version finale n'impose pas de comptage de mots : ses formulations sont courtes
par construction et restent intégralement soumises à la revue de pertinence.

## 5. JSON Schema et validation Pydantic

JSON Schema décrit la forme d'un objet JSON. Pydantic permet de définir ce contrat
avec des classes Python, de produire le schéma (`model_json_schema`) et de valider
du JSON (`model_validate_json`). Le même contrat sert donc à guider le modèle
et à rejeter une sortie incorrecte au retour.

Les `Literal` limitent les valeurs admises, par exemple `haute`, `moyenne`, `basse`.
`strict=True` évite les conversions trompeuses, comme `"true"` vers `True`.
`extra="forbid"` rejette une clé non prévue. `Field` borne la longueur des textes.
`model_validator` de `Resultat` contrôle plusieurs champs ensemble.

Ce contrat vérifie la structure et certains invariants, pas la vérité factuelle,
la bonne catégorie ni la langue réelle du texte. Le contrôle du résumé est une
heuristique de ponctuation et non une analyse linguistique : une abréviation peut
déclencher un refus. La pertinence est examinée dans l'évaluation et la revue.

## 6. Rôle de l'orchestrateur

Un orchestrateur coordonne des étapes. Ici `traiter_email` suit un chemin explicite,
sans boucle de décision autonome :

```text
vérifier le texte
→ analyser avec le modèle
→ appliquer les règles Python
→ proposer des formulations et laisser le modèle en choisir une si nécessaire
→ construire le résultat cohérent
```

`traiter_lot` est la boucle externe sur les fichiers. `OllamaLLM` s'occupe du
transport et des sorties structurées. Cette séparation permet de tester le
parcours sans modèle et de réutiliser `traiter_email` dans une future interface.

## 7. Pourquoi deux appels au même modèle ?

Le premier doit prendre des décisions discrètes et courtes. Le second choisit
une réponse complète à partir de ces décisions. Les séparer permet de ne pas rédiger pour le spam,
d'appliquer les invariants avant la réponse et de distinguer erreur d'analyse
et erreur de rédaction. Les inconvénients sont la latence et la possibilité que
le second appel propage une analyse erronée. Le texte original reste fourni
au second appel pour qu'il puisse choisir le thème et la question appropriés.
Après deux essais libres insuffisants, le texte est fermé par une enum. Cela réduit
la personnalisation. Le second appel apporte moins de valeur qu'une rédaction
libre ; il conserve le format à deux appels demandé. Une variante future sans
cette contrainte pourrait sélectionner ces messages par règles sans modèle.

## 8. Règles appliquées dans Python

Python contrôle ce qui doit être garanti : un spam n'a jamais de brouillon,
les signaux sensibles imposent une revue, les noms de fichiers viennent de
l'entrée, le lot est stable et les erreurs techniques ne deviennent pas `autre`.
Les expressions régulières sont un filet indépendant du modèle, pas une vérité
sémantique : « aucun remboursement demandé » peut déclencher une revue
excessive. C'est un compromis conservateur à expliquer et à améliorer.

Le modèle traite le sens et choisit une formulation contrôlée. Les règles Python
recalculent aussi toutes les priorités selon la politique documentée : spam bas,
cas sensible/démo haut, candidature/sans réponse/support non urgent bas, sinon
moyen. Ce sont des décisions de l'application après modèle. Elles ne cachent pas une table
de catégories associées aux 20 noms de fichiers ; les annotations ne sont jamais
chargées par le programme de traitement.

## 9. Gestion des erreurs

Une exception interrompt la fonction courante. `ErreurTraitement` porte un code
stable et un message ; `traiter_lot` la transforme en ligne d'erreur puis continue.
Les problèmes de dossier ou d'écriture sont globaux et remontent au CLI.
Les erreurs inattendues de programmation ne sont pas avalées par un `except`
général, ce qui les rend visibles pendant le développement.

La reprise est bornée : un premier JSON invalide entraîne un retour correctif,
un second échec arrête cet email. Un timeout, une connexion refusée ou un modèle
absent n'est pas répété automatiquement. Un problème de brouillon conserve
l'analyse dans `Echec.analyse` mais compte comme échec complet pour les scores.

À la relance, le manifeste permet de retirer un vieux brouillon, même si le
fichier est maintenant en erreur. Les empreintes protègent les retouches humaines.
Les écritures atomiques protègent un fichier isolé, sans assurer une transaction
sur l'ensemble du dossier ni la prise en charge de deux exécutions concurrentes.

## 10. Calcul et interprétation des métriques

L'évaluation commence par joindre référence et prédictions **par nom**, pas par
position. Les doublons sont refusés. Un résultat manquant ou en erreur ne reçoit
pas une catégorie factice : il réduit la couverture et figure dans les anomalies.

Pour une catégorie donnée, VP désigne les vrais positifs, FP les faux positifs et
FN les faux négatifs. Précision = VP/(VP+FP), rappel = VP/(VP+FN),
F1 = 2×précision×rappel/(précision+rappel). Une division indéfinie vaut zéro ici.
La macro F1 donne le même poids à chaque catégorie ; l'exactitude donne le même
poids à chaque email. Une classe absente garde F1=0 dans la moyenne des huit
classes, conformément au choix explicite du code.

Les quatre cas sensibles de la référence (`05`, `07`, `18`, `19`) sont examinés
aussi sur le booléen de revue : un bon classement peut malgré tout oublier la
revue humaine. Les échecs techniques sur ces cas sont listés comme non évalués,
sans être assimilés à des revues correctement demandées.

Les scores restent provisoires tant que Bochra n'a pas validé les annotations.
Le même lot ayant servi à lire les cas et construire les prompts, il ne mesure
pas la performance sur des emails nouveaux. Une excellente classification ne
garantit pas des brouillons utilisables : appliquer la grille dédiée.

## Questions probables au débrief

**Pourquoi ce modèle ?** C'est le candidat demandé, bilingue et compact. Ses poids
Q4_K_M d'environ 2,5 Go permettent de l'essayer sur cette machine. Les observations
réelles, y compris les limites matérielles, figurent dans `docs/verification.md`.

**Pourquoi pas LangChain ?** Le besoin est une chaîne de deux appels et des
fichiers locaux. Quelques fonctions explicites rendent les choix et les erreurs
plus faciles à expliquer, sans ajouter de couche utile uniquement à plus grande
échelle.

**Pourquoi ne pas classer par mots-clés ?** « Démo », « walkthrough » et « voir la
solution en action » expriment une intention commune de façons différentes.
Le modèle traite ce sens. Les mots-clés servent seulement à déclencher des revues
conservatrices sur des signaux importants.

**Que garantissez-vous sur les inventions ?** Dans les brouillons, le modèle peut
uniquement renvoyer un texte du catalogue prudent de `redaction.py`. L'enum est
vérifiée dans Python : une phrase libre sur le RGPD ou un remboursement est refusée.
Cela ne garantit pas la pertinence de la variante choisie ni l'analyse. Les champs
restent à compléter et la revue humaine demeure nécessaire. Une base produit
approuvée permettrait ensuite des réponses plus riches et étayées.

**Que se passe-t-il si le modèle retourne un champ de trop ?** Pydantic refuse la
sortie, l'appel est corrigé une fois, puis l'email devient une erreur si nécessaire.

**L'email peut-il changer les règles de l'agent ?** Il est transmis comme donnée
dans un rôle utilisateur, sous des règles système. Le modèle n'a aucun outil
permettant d'envoyer, d'exécuter ou de naviguer. Il reste possible qu'il produise
un mauvais classement sous l'effet d'une injection ; le test de séparation des
messages ne démontre pas une résistance sémantique universelle.

**Pourquoi une démo est-elle haute et une candidature basse ?** C'est une
hypothèse commerciale documentée, inspirée de l'exemple du PDF pour les démos.
Elle doit être validée avec l'équipe ; la rendre explicite permet de la discuter.

**Comment la reprise évite-t-elle les boucles ?** Deux tentatives maximum pour
un contenu invalide. Aucune reprise automatique d'une panne réseau.

**Que veut dire 100 % sur ces emails ?** Seulement que les décisions correspondent
à cette petite référence, pour les fichiers effectivement traités. Ce n'est ni une
certification de qualité rédactionnelle, ni une mesure de généralisation, ni une
référence validée si son statut reste provisoire.

**Quels tests sont les plus utiles ?** Le spam annoncé à tort comme nécessitant
une réponse, le signal sensible oublié par le modèle, le lot avec un email vide,
et la relance après une modification : ils testent les garanties de l'application
quelles que soient les qualités linguistiques du modèle.

**Que changer pour la production ?** Un jeu de test séparé et validé, une base
factuelle approuvée, une meilleure détection sensible et des attaques réelles,
des écritures de lot transactionnelles et un mécanisme explicite d'approbation
des brouillons. Ces éléments ne sont pas annoncés comme déjà implémentés.
