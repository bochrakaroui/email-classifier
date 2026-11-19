# Revue des sorties finales par Codex

Statut : revue de développement par l'assistant, **pas validation par Bochra**.
La grille `grille_revue.md` doit encore être remplie par une personne. Les textes
finals ont été lus après la seconde exécution complète et comparés au catalogue.

Les 17 brouillons sont dans la langue détectée, professionnels, courts, avec
signature exacte et champ pertinent. Aucun tarif, disponibilité, délai, menu
produit, conformité RGPD, poste ouvert, absence de programme, remboursement ou
participation n'y est inventé. Ils ne prétendent pas avoir lu de pièce jointe.
Les textes n'ont pas été corrigés manuellement dans `outputs/` : ils sont les
réponses réelles du modèle, bornées par l'enum.

| Emails | Observation de revue | Information à compléter |
|---|---|---|
| 01, 02, 16 | Demande de démo reconnue ; aucune confirmation de créneau. | Disponibilités réelles FAKTUS. |
| 03 | Variante tarifs/intégrations pertinente, sans prix ni connecteur affirmé. | Tarifs et compatibilités approuvés. |
| 04 | Variante sécurité pertinente, en anglais, sans conformité affirmée. | Hébergement, RGPD, DPA/documents. |
| 05 | Accusé d'incident bloquant prudent ; demande de capture expurgée. | Prise en charge et suite réelles. |
| 06 | Accusé de support générique ; ne prétend pas expliquer la cause. | Réponse utile sur l'export CSV. |
| 07, 19 | Problème attribué au signalement ; vérification avant toute décision. | Explication et décision après contrôle. |
| 08 | Accusé de demande de mise à jour, sans action annoncée comme faite. | État réel de la mise à jour. |
| 09, 10 | Remerciement pour la collaboration, sans programme ni conditions inventés. | Contact et modalités approuvés. |
| 11, 12 | Accusé de candidature, aucune consultation de CV prétendue. | Opportunités et suite RH. |
| 15 | Invitation avec intérêt/disponibilités laissés ouverts. | Décision de participation à l'événement. |
| 17 | Aucun menu ou chemin produit inventé ; réponse très générique. | Procédure support réelle. |
| 18 | Participation à l'appel d'offres laissée à confirmer. | Décision et interlocuteur. |
| 13, 14, 20 | Aucun brouillon : deux spams et une newsletter. | Sans objet. |

Le compromis est visible : les réponses sont des bases prudentes à compléter,
pas des réponses produit autonomes. Elles ne reprennent pas librement les noms,
montants, dates ou adresses ; cela évite les altérations constatées dans les essais
libres, mais réduit la personnalisation.

La prose de l'analyse reste générée librement. Imprécisions observées et non
couvertes par les scores de classification : `08` parle de futurs « bons de
commande » au lieu de factures ; la justification de `20` invente une fréquence
« bimonthlière » ; certains résumés présentent une affirmation d'expéditeur sans
l'attribuer explicitement (`07/19`) ou qualifient un prospect de client (`02`).
Les mentions de CV joint (`11/12`) ne prouvent pas la présence d'une pièce jointe.
Ces textes doivent être relus avant d'être utilisés comme faits. Le contrôle
d'une phrase est syntaxique et ne corrige pas ces imprécisions sémantiques.

Hors corpus, le test bilingue échoue sur la langue ; le test d'injection unique
réussit. Aucun des deux ne permet de généraliser. Voir `robustesse_reelle.json`.
