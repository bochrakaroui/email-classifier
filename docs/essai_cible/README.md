# Essai ciblé de rédaction libre : rejeté

Le deuxième essai a traité réellement `04`, `12`, `15`, `17`, `18` avec un prompt
plus court, un champ par catégorie et une langue explicite. Les cinq sorties
étaient structurellement valides. Le classement de l'appel d'offres et la réponse
à l'invitation étaient corrigés, mais les brouillons `04` et `18` affirmaient encore
la conformité RGPD et la participation à l'appel d'offres sans information fournie.
Ces résultats ont été rejetés. Ils restent ici comme preuve du changement de
conception, sans être présentés comme sorties finales ou comme modèles à suivre.

La version livrée remplace la rédaction libre par le choix d'un texte complet
dans une liste finie construite dans `redaction.py` et imposée par une enum JSON
Schema/Pydantic. Un troisième contrôle ciblé a confirmé l'absence de ces phrases
dans les cinq brouillons contraints. La relance complète est documentée dans le
journal de vérification.
