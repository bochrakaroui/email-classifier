# Premier essai réel : résultats provisoires rejetés en revue

Ces fichiers sont une archive de vérification, **pas les sorties finales**.
Ils ont été produits avant la correction des prompts et le contrôle d'une phrase
unique pour le résumé. Le schéma courant peut donc refuser certains anciens
résultats ; `evaluation.json` conserve l'évaluation réellement effectuée alors.

Mesures : 20 succès techniques / 0 échec, 36 appels, 956,516 secondes, exactitude
et macro F1 de 0,95 sur les annotations proposées. Une erreur de catégorie sur
l'appel d'offres `18`, quatre erreurs de priorité et une réponse omise sur
l'invitation `15`. Aucun faux négatif/positif sur les quatre revues sensibles.

Revue par Codex des 16 brouillons : plusieurs résultats non utilisables, notamment
`04` (mauvaise langue et conformité RGPD inventée), `17` (menus produit inventés),
`09/10/12` (absence de programme ou poste inventée), `11` (champs sans rapport et
pièce jointe tenue pour disponible), `19` (montant dit confirmé), champs anglais
dans des réponses françaises et délais non fournis. Plusieurs résumés avaient
deux phrases. Ces défauts ont motivé une correction et une nouvelle exécution.

`prompts.py.txt` conserve les consignes exactes de ce premier essai.
Les données originales et les annotations n'ont pas été modifiées pour améliorer
artificiellement les scores. Ce corpus sert de développement, pas de test séparé.
