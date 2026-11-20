"""Formulations prédéfinies : aucune connaissance produit ou décision inventée.

Le deuxième appel choisit un texte complet de cette liste par un schéma à enum.
La variété concerne le ton, le thème et les questions, jamais des faits FAKTUS.
"""

from schemas import Analyse


def propositions_brouillons(analyse: Analyse) -> list[str]:
    anglais = analyse.langue == "en"
    categorie = analyse.categorie
    if "appel_offres" in analyse.cas_sensibles:
        textes = [
            "Merci pour votre invitation à répondre à cet appel d'offres. Notre participation reste à confirmer.\n\n[DÉCISION DE PARTICIPATION ET CONTACT À COMPLÉTER]",
            "Thank you for inviting us to respond to your tender. Our participation remains to be confirmed.\n\n[PARTICIPATION DECISION AND CONTACT TO ADD]",
        ]
    elif "incident_bloquant" in analyse.cas_sensibles:
        textes = [
            "Merci pour votre message. Vous signalez un incident bloquant ; nous prenons note de l'urgence de votre demande.\n\n[PRISE EN CHARGE ET SUITE À CONFIRMER]\n\nPourriez-vous préciser l'heure de début et transmettre une capture du message d'erreur, sans données sensibles ?",
            "Thank you for your message. You report a blocking incident, and we acknowledge the urgency of your request.\n\n[HANDLING AND NEXT STEPS TO CONFIRM]\n\nCould you share the start time and a screenshot of the error, with sensitive information removed?",
        ]
    elif "litige_facturation" in analyse.cas_sensibles:
        textes = [
            "Merci pour votre message concernant le problème de facturation que vous signalez. Les éléments doivent être vérifiés avant de confirmer une explication, un avoir ou un remboursement.\n\n[SUITE À CONFIRMER APRÈS VÉRIFICATION]",
            "Thank you for your message about the billing issue you report. The details need to be verified before an explanation, credit note or refund can be confirmed.\n\n[NEXT STEPS TO CONFIRM AFTER VERIFICATION]",
        ]
    else:
        textes = {
            "demo": [
                "Merci pour votre intérêt et votre demande de démonstration.\n\n[CRÉNEAUX FAKTUS À CONFIRMER]\n\nCes propositions restent à compléter selon les disponibilités de notre équipe.",
                "Thank you for your interest and your request for a demonstration.\n\n[FAKTUS AVAILABILITY TO CONFIRM]\n\nThese proposed slots need to be completed based on our team's availability.",
            ],
            "question_commerciale": [
                "Merci pour vos questions concernant notre solution.\n\n[RÉPONSE COMMERCIALE VALIDÉE À COMPLÉTER]",
                "Thank you for your questions about our solution.\n\n[VERIFIED COMMERCIAL ANSWER TO ADD]",
            ],
            "support": [
                "Merci pour votre demande d'aide.\n\n[RÉPONSE SUPPORT VALIDÉE À COMPLÉTER]",
                "Thank you for your request for help.\n\n[VERIFIED SUPPORT GUIDANCE TO ADD]",
            ],
            "facturation": [
                "Merci pour les informations de facturation communiquées et votre demande de mise à jour.\n\n[MISE À JOUR ET SUITE À CONFIRMER]",
                "Thank you for the billing information provided and your update request.\n\n[UPDATE AND NEXT STEPS TO CONFIRM]",
            ],
            "partenariat": [
                "Merci pour votre proposition de collaboration et l'intérêt porté à notre équipe.\n\n[CONTACT ET MODALITÉS DE PARTENARIAT À CONFIRMER]",
                "Thank you for your collaboration proposal and your interest in our team.\n\n[PARTNERSHIP CONTACT AND TERMS TO CONFIRM]",
            ],
            "candidature": [
                "Merci pour votre candidature et votre intérêt pour notre équipe.\n\n[OPPORTUNITÉS ET SUITE À CONFIRMER]",
                "Thank you for your application and your interest in our team.\n\n[OPPORTUNITIES AND NEXT STEPS TO CONFIRM]",
            ],
            "autre": [
                "Merci pour votre invitation et l'intérêt porté à notre équipe.\n\n[INTÉRÊT ET DISPONIBILITÉS À CONFIRMER]",
                "Thank you for your invitation and your interest in our team.\n\n[INTEREST AND AVAILABILITY TO CONFIRM]",
            ],
        }[categorie]
    corps = textes[1] if anglais else textes[0]
    # Variantes spécifiques utiles ; le modèle choisit selon la demande originale.
    variantes = [corps]
    if categorie == "question_commerciale" and not analyse.cas_sensibles:
        variantes.append(
            "Thank you for your questions about data hosting, GDPR compliance and security documentation.\n\n[VERIFIED HOSTING, GDPR AND DOCUMENTATION INFORMATION TO ADD]" if anglais else
            "Merci pour vos questions sur l'hébergement, la conformité RGPD et la documentation de sécurité.\n\n[INFORMATIONS VALIDÉES SUR HÉBERGEMENT, RGPD ET DOCUMENTATION À COMPLÉTER]"
        )
        variantes.append(
            "Thank you for your questions about pricing and integrations.\n\n[VERIFIED PRICING AND INTEGRATION INFORMATION TO ADD]" if anglais else
            "Merci pour vos questions sur les tarifs et les intégrations.\n\n[TARIFS ET INTÉGRATIONS VALIDÉS À COMPLÉTER]"
        )
    if categorie == "support" and not analyse.cas_sensibles:
        variantes.append(corps + ("\n\nCould you share a screenshot of the issue with sensitive information removed?" if anglais else
                                  "\n\nPourriez-vous joindre une capture du problème, sans données sensibles ?"))
    debut = "Hello,\n\n" if anglais else "Bonjour,\n\n"
    fin = "\n\nBest regards,\nThe FAKTUS team" if anglais else "\n\nCordialement,\nL'équipe FAKTUS"
    # Deux tons possibles sans changement de faits ni de décision.
    return [debut + t + fin for t in variantes] + [
        ("Dear Sir or Madam,\n\n" if anglais else "Madame, Monsieur,\n\n") + corps + fin
    ]
