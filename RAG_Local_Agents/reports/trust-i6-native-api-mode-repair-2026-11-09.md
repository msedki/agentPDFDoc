# I6 — correction de l’enveloppe API de la recette native

**Rôle :** incident de préparation, correctif et gel de reprise distinct.
**Propriétaire :** intégration et qualification RAG.
**Statut :** correctif logiciel vérifié ; nouvelle campagne native à exécuter.
**Date :** 9 novembre 2026 (UTC).
**Référence produit :** `26a0eb80b0a637c2ea21a5bd4155c16d3648e612`.

## Incident observé et preuves conservées

Le premier bloc de reprise v1 a terminé 11 positions de référence. La douzième,
N_I6D35, a été rejetée par `QueryRequest` avant création d’une requête : elle
portait deux sujets dans un seul document, alors que le mode API `comparison`
exige de deux à quatre documents. Les six positions suivantes n’ont pas été
exécutées. Cette erreur n’est ni une réponse applicative ni un résultat négatif
mesuré sur l’oracle documentaire.

Les trois groupes de processus possédés sont arrêtés, sans membre restant ;
les sources et le GGUF partagé sont inchangés. Les 11 réponses terminées ont
été relues contre les sources et annotations gelées : leurs littéraux, liens
sujet/document, exceptions et citations sont conservés dans les champs examinés.
La tentative garde néanmoins son état interrompu et son dénominateur de 18.
Les [preuves v1](trust-i6-native-recovery-v1-2026-11-09.json.gz) et leur
[inventaire](trust-i6-native-recovery-v1-collection-2026-11-09.json) restent
séparés de la reprise.

## Correction et recette v2

Le préparateur valide désormais chacune des 18 enveloppes via le véritable
`QueryRequest` avant de matérialiser des originaux. Une comparaison dans un
seul document utilise le mode `question` uniquement lorsque la question
établit déjà une comparaison entre plusieurs sujets. Les validations publiques
continuent à refuser un mode comparaison ordinaire avec un seul document,
ou une comparaison entre plus de quatre documents.

Seul N_I6D35 change de mode API. La recette v2 conserve ses deux sujets,
son unique document, ses deux paragraphes et sa conclusion attendue. Elle
consigne le mode de la fixture et la raison de l’ajustement. Le schéma et
l’identifiant de protocole différencient cette recette de v1.

La reprise réutilise les 23 originaux et les six extractions PDF octet pour
octet. Les empreintes, questions, périmètres, annotations et regroupements
sont comparés avant le nouveau gel ; aucun second document n’est fabriqué.
Les témoins supplémentaires et les deux recettes HTTP restent les mêmes.

## Validation

Le nouveau contrôle échoue d’abord sur l’enveloppe N_I6D35 de la version
antérieure. Après correction, **106 tests ciblés passent**, dont trois nouveaux
contrôles ; Ruff passe sur le périmètre complet et Mypy sur 155 fichiers.
Le test de N_I6D35 fait aussi exécuter le vrai contrat et le rendu en mode
`question`, puis applique l’oracle existant aux valeurs, comparaisons,
littéraux et citations. Son compteur de tokens reste un double déclaré.

Une assertion intermédiaire attendait une liste là où le contrat expose un
tuple de sujets : le journal de cette erreur de test est conservé, puis
l’attente de type a été corrigée en gardant les mêmes identités. Les résultats
et commandes sont dans le [reçu de validation](trust-i6-native-api-mode-validation-2026-11-09.json)
et les [preuves logicielles](trust-i6-native-api-mode-evidence-2026-11-09.json.gz).
La revue indépendante du préparateur ne relève pas de défaut bloquant.

La suite portable de 5 397 tests et le benchmark DEV du
[lot R3](trust-i6-r3-2026-11-09.md) restent rattachés à ses sources produit,
qui sont inchangées dans ce correctif de préparation. Le
[reçu de publication R3](trust-i6-r3-publication-2026-11-09.json) vérifie
l’égalité des arbres et parents locaux/distants.

## Reprise et limites

La campagne v2 sera gelée sur le commit publié du présent lot. Ses résultats
seront distincts de la tentative v1, avec les 18 positions initiales, les deux
témoins directs supplémentaires et les deux parcours HTTP séparés pour chaque
bras. Les délais, quotas et critères du protocole I6 restent applicables.
Le jeu FINAL historique demeure indisponible et n’a pas été reconstruit.
