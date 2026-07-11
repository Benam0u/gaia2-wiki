# Gaia 2 - Wiki de campagne (living doc)

Wiki personnel de la campagne JDR Gaia 2 (personnage ZogZork). Source de verite du STATUT projet.

## Statut

- 2026-07-11 : **v1 LIVREE** - build core (52 tests) + import complet (111 fiches) + review adversariale (25 findings corriges) + acceptation spec section 16 passee. EN ATTENTE : relecture du contenu par Benoit (l'import est fidele aux PDFs du 2026-07-10 ; ses souvenirs priment sur les PDFs).
- 2026-07-10 : spec de design validee -> `docs/2026-07-10-wiki-gaia2-spec.md` ; plan -> `docs/plans/2026-07-11-wiki-implementation.md`.

## Utilisation

- Consulter : double-clic sur `wiki.html` (complet) ; partager au MJ/joueurs : envoyer `wiki_partage.html` (sans fiches `prive: true` ni blocs `%%...%%`).
- Rebuild apres edition : `python3 build_wiki.py` depuis `Gaia2/` (0.1 s, rapport de coherence en console).
- Post-session, deux modes : dicter les notes en vrac a Claude (il met a jour fiches + `sessions/session-NN.md` + rebuild, relire le diff git), ou editer les .md soi-meme puis rebuild. Prochaine session = 21, template `wiki/sessions/_template.md`.
- GARDE-FOU : un `%%` non ferme fait ECHOUER le build (fail-closed, rien n'est ecrit) - corriger la fiche indiquee puis relancer.
- `scripts/extract_systeme.py` : NE PAS relancer sans raison, il ecrase les fiches systeme (voir son en-tete).

## Decisions cles

- Single-file `wiki.html` + `wiki_partage.html`, design system exact de board.html (sombre chaud + or, Fraunces/Inter/JetBrains Mono), images dedupliquees en JPEG (1.4 MB par fichier).
- Sources = un .md par fiche dans `wiki/`, wikilinks `[[...]]` (resolution titre H1 puis alias, insensible casse/accents), backlinks calcules, liens morts = moteur de croissance (listes sur l'accueil).
- Confiance : confirme / hypothese / fragment ; etats d'affaires EN COURS / RESOLU / FERME ; `ne-pas-fusionner` affiche en avertissement.
- Chronologie deux regimes : 14 periodes reconstituees (passe) + journal par session (futur).
- Fiche ZogZork : narratif dans le md, technique generee depuis `data/zogzork_profile.json` (re-exporter apres level-up, remplacer, rebuild).

## Sources externes (import du 2026-07-11)

- `/mnt/c/Users/benoi/OneDrive/Bureau/Dev/Character_Sheet/Gaia_2_Dossier_detaille_ZogZork_2026-07-10.pdf` (principal)
- `/mnt/c/Users/benoi/OneDrive/Bureau/Dev/Character_Sheet/Recap_Gaia_2_ZogZork_2026-07-10_v3.pdf`
- `/mnt/c/Users/benoi/OneDrive/Bureau/Dev/Character_Sheet/ZogZork_profile_level3_Juillet.json`
- `/mnt/c/Users/benoi/OneDrive/Bureau/Dev/WeakAuction/project_cursor/Projet_Weak_Auctions/JDR/` (characterData + img/)

## Next

1. Relecture du wiki par Benoit (verif visuelle du look incluse, + rendu mobile de la nav) ; corrections de memoire par dictee ou edition directe.
2. Session 21 : premier tour du workflow post-session en mode dictee.
3. Idees v2 notees dans la spec section 15 (hover-cards, graphe de relations, tri "recemment modifiees" par date git plutot que mtime).
