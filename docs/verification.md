# Vérification et limites du rendu

Le rendu contient une exécution réelle sur les 20 emails fournis, des tests du
code et des observations de limites. Les annotations de référence restent
**à valider par Bochra** : les scores sont des résultats de développement.

## Résultats livrés

Le passage réel du **20 novembre 2026** utilise Ollama et
`qwen3:4b-instruct-2507-q4_K_M`, avec le traitement complet : analyse, règles
Python et sélection d’un brouillon si nécessaire.

| Mesure | Résultat observé |
| --- | --- |
| Emails traités avec succès | 20 sur 20 |
| Erreurs techniques | 0 |
| Brouillons | 17 ; aucune réponse pour les spams et la newsletter |
| Appels au modèle | 41, dont quatre reprises de validation réussies |
| Durée du lot sur CPU | 881,273 secondes, soit environ 14 min 41 s |
| Catégories conformes à la référence proposée | 20 sur 20 |
| Couverture, exactitude et macro F1 | 1,00 sur ce lot |
| Écarts de langue, priorité, réponse et revue humaine | Aucun sur les décisions annotées |

Les fichiers à consulter sont :

- [Analyses et brouillons](../outputs/resultats.json).
- [Métriques de l’exécution et empreintes des entrées](../outputs/execution.json).
- [Évaluation détaillée](../outputs/evaluation.json).
- [Brouillons en texte](../outputs/reponses/) et
  [manifeste de protection des retouches](../outputs/manifest.json).

La priorité est haute pour `05`, basse pour `13`, `14`, `15` et `20`,
et moyenne pour les quinze autres, selon la règle métier documentée dans le README.
La priorité et la revue humaine sont indépendantes.

Cette durée est une observation unique sur la machine d’essai, pas un benchmark
contrôlé. Elle dépend notamment du matériel, du chargement et de l’état du cache.

## Reproduire les vérifications

Depuis la racine du projet, sous PowerShell :

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe evaluate.py --reference annotations.json --predictions outputs/resultats.json --output tmp/evaluation_controle.json
```

La première commande teste le code sans lancer Ollama. La seconde vérifie les
résultats livrés, sans nouvelle génération. Pour une nouvelle exécution réelle :

```powershell
.\.venv\Scripts\python.exe main.py --input emails --output tmp/nouvel_essai
```

Sur Linux/macOS, remplacer `.\.venv\Scripts\python.exe` par `./.venv/bin/python`.
Le dossier `tmp/` est créé au besoin et reste exclu de Git.

## Tests du code et conservation du comportement

La suite compte **156 tests réussis**. Elle couvre notamment les erreurs isolées,
les catégories et types autorisés, l’identité, les phrases brèves, les priorités,
les cas sensibles, la protection des brouillons retouchés et les interactions
de l’interface. Les tests Streamlit passent par AppTest ; seul le transport
vers Ollama est simulé.

Après simplification du code, les réponses enregistrées du dernier passage réel
ont été rejouées dans les versions antérieure et simplifiée. Pour les **20 emails**,
les **41 requêtes**, reprises comprises, et les **17 brouillons** sont identiques.
La comparaison vérifie les messages, schémas JSON, paramètres et résultats.

Le [rapport de relecture](relecture_simplification.json) conserve les empreintes
des sources et le résultat par email. C’est une relecture de réponses réelles
enregistrées, sans nouvelle inférence ni nouvelle mesure de latence. Les fichiers
d’exécution livrés gardent les métadonnées de leur génération d’origine.

### Reprise d’un lot interrompu dans l’interface

Un test a reproduit le symptôme « 5 traités, 0 erreur » : une relance automatique
du script au sixième email interrompait la boucle déclenchée par le bouton, et
la liste restante n’était pas mémorisée. Les journaux Ollama de la session
signalée montrent des réponses HTTP 200 ; les anciens rapports ne contenaient
que les erreurs, sans progression. Le déclencheur exact de la relance automatique
sur la machine n’a pas été identifié.

Le lot et sa progression sont maintenant conservés dans la session. Le résultat
et le retrait de l’email de la file sont enregistrés avant tout nouvel affichage.
`runner.fastReruns=false` évite le lancement concurrent d’une nouvelle exécution
pendant cette sauvegarde. Les compteurs sont actualisés après chaque email ;
le suivi apparaît au-dessus du tableau. Un bouton permet d’arrêter explicitement
le lot, et le journal local conserve l’état, l’email courant et les fichiers restants.
Cette reprise concerne la même session ; elle ne remplace pas une sauvegarde
persistante des corrections après arrêt du serveur.

Lors de cette première correction : **153 tests réussis en 20,72 s**, dont quatre nouveaux tests :
relance au sixième email, relance demandée pendant un appel sans retraitement
d’un email terminé, conservation d’une erreur sans réessai automatique et arrêt
explicite du lot. Les tests existants de corrections humaines restent réussis.

Les 20 fichiers réels ont aussi été rejoués dans AppTest avec les réponses
enregistrées : **20 succès, 0 erreur, 17 brouillons, 41 requêtes identiques**,
avec une relance au sixième email et aucun email retraité. Ce contrôle ne fait
pas de nouvel appel au modèle. Le backend d’analyse et de rédaction est inchangé ;
le [rapport de reprise](reprise_interface.json) conserve le détail et les empreintes
de la nouvelle interface. Le rapport de simplification précédent décrit la
version antérieure de l’interface.

### Consultation des résultats et sauvegarde des corrections

Deux scénarios supplémentaires ont été reproduits avant correction : le callback
du brouillon levait le `KeyError` signalé lorsque sa clé de widget avait disparu ;
le rejeu d’un ancien déclencheur « Réanalyser » lançait une nouvelle analyse sans
nouveau clic. Le test simule ce rejeu avec le mécanisme de relance de Streamlit ;
il ne constitue pas une capture des événements exacts du navigateur de Bochra.

La sauvegarde ignore désormais une valeur de champ absente et conserve la dernière
correction enregistrée ; une chaîne vide reste une correction valide. Les trois
boutons d’analyse créent leur lot dans `on_click`. Leur valeur de retour lors d’un
réaffichage ne déclenche plus de traitement. Ce choix suit le
[fonctionnement des callbacks Streamlit](https://docs.streamlit.io/develop/concepts/architecture/widget-behavior#order-of-operations).

Les trois nouveaux tests couvrent ces deux scénarios et la consultation des 20
résultats, avec édition puis retour au premier email : aucun appel supplémentaire,
aucune remise à zéro du lot et corrections conservées. Les tests de réanalyse
explicite et de reprise des lots restent réussis. La suite complète passe :
**156 tests réussis en 23,36 s**. Le rapport de reprise est
actualisé avec le contrôle de consultation sur les 20 emails réels rejoués.

## Choix motivés par les essais

**Rédaction contrôlée.** Les essais de rédaction libre ont produit des affirmations
non étayées, notamment sur la conformité RGPD, des menus du produit et des décisions
commerciales. La réponse finale est donc choisie dans un catalogue de textes
autorisés. Ce contrôle réduit les inventions de texte, avec moins de personnalisation ;
une mauvaise analyse peut encore conduire au choix d’un texte peu pertinent.

**Identité.** Avant correction, un passage réel a donné 16 succès et quatre échecs
de validation (`07`, `13`, `14`, `20`). Les contrôles exigeaient parfois une
entreprise répétée ou refusaient une variante de service pourtant présente dans
la signature. La normalisation utilise maintenant les informations explicites,
tout en conservant les refus d’une autre personne ou d’une société inventée.
Les [réponses refusées et messages correspondants](rejets_avant.json) sont conservés
pour expliquer cette correction. Ces quatre échecs reproduits ne permettent pas
d’identifier rétrospectivement toutes les erreurs d’une ancienne session d’interface.

**Modèle local.** Le [diagnostic initial](diagnostic_modele.json) relève un modèle
de 4 milliards de paramètres, quantifié en `Q4_K_M`, d’environ 2,5 Go sur disque.
Ollama rapportait environ 3,2 Go pour le modèle chargé, sans mémoire GPU utilisée.
Ce diagnostic date du 19 novembre ; sa réponse synthétique illustre une ancienne
version des consignes, pas le contrat actuel des résumés.

**Langue et instructions malveillantes.** Les
[deux essais synthétiques historiques](robustesse_reelle.json) ont correctement
classé une publicité contenant une instruction de détournement, mais ont détecté
à tort en français une demande bilingue principalement anglaise. Ils concernent
une version antérieure ; aucune résistance générale aux injections ni maîtrise
générale du bilinguisme n’est revendiquée.

## Limites et relecture nécessaire

Les annotations ont été proposées par l’assistant avant les prédictions ; leurs
priorités ont ensuite suivi la règle demandée par Bochra. Elles ne sont jamais
chargées par le traitement des emails. Un petit jeu de développement et une
référence non validée ne mesurent pas la généralisation.

La réussite technique ne garantit pas la fidélité de la prose. Dans les résultats
livrés, `03` assimile maladroitement une personne à sa PME, `04` attribue à
Lukas Becker un rôle dans la conformité non établi par le message, et `16`
reformule de façon imprécise le contexte temporel du salon. Le nom « Microsoft »
dans le phishing `14` reste une identité déclarée, pas une identité authentifiée.

Avant d’utiliser une réponse, vérifier sa pertinence, sa langue, les affirmations,
les champs à compléter et les alertes de revue humaine. Aucun email n’est envoyé
automatiquement. La connexion Gmail reste non configurée.

Les prochaines améliorations seraient de faire valider la référence et de tester
un lot indépendant, de disposer d’une documentation produit approuvée pour
personnaliser les réponses, puis d’évaluer les cas bilingues et les performances
sur plusieurs exécutions contrôlées.
