# Gaia 2 - Wiki de campagne (living doc)

Wiki personnel de la campagne JDR Gaia 2 (personnage ZogZork). Source de verite du STATUT projet.

## Statut

- 2026-07-10 : spec de design validee par Benoit -> `docs/2026-07-10-wiki-gaia2-spec.md`. Mise en prod PAS lancee (sur demande de Benoit plus tard).

## Decisions cles

- Single-file `wiki.html` (pattern board.html Horde) + `wiki_partage.html` filtre (flag `prive`, blocs `%%`).
- Sources = un .md par fiche dans `wiki/`, wikilinks `[[...]]`, backlinks calcules au build.
- Niveaux de confiance : confirme / hypothese / fragment ; etats d'affaires EN COURS / RESOLU / FERME ; garde-fou `ne-pas-fusionner`.
- Chronologie deux regimes : periodes reconstituees (passe) + journal par session (a partir de la session 21).
- Section Systeme complete (20 races, 13 classes, 52 competences, 15 avantages) extraite du createur de fiche ; fiche ZogZork generee depuis `data/zogzork_profile.json`.
- Style : design system exact de board.html (sombre chaud + or, Fraunces/Inter/JetBrains Mono).

## Sources externes (a l'import)

- `/mnt/c/Users/benoi/OneDrive/Bureau/Dev/Character_Sheet/Gaia_2_Dossier_detaille_ZogZork_2026-07-10.pdf` (principal, 12 p.)
- `/mnt/c/Users/benoi/OneDrive/Bureau/Dev/Character_Sheet/Recap_Gaia_2_ZogZork_2026-07-10_v3.pdf`
- `/mnt/c/Users/benoi/OneDrive/Bureau/Dev/Character_Sheet/ZogZork_profile_level3_Juillet.json`
- `/mnt/c/Users/benoi/OneDrive/Bureau/Dev/WeakAuction/project_cursor/Projet_Weak_Auctions/JDR/` (characterData dans index.html + img/, ignorer Obsolete/)

## Next

1. Relecture de la spec par Benoit.
2. A sa demande : plan d'implementation (writing-plans) puis mise en prod (build core -> import -> relecture -> session 21 en mode dictee).
