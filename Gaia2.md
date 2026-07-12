# Gaia 2 - Wiki de campagne (living doc)

Wiki personnel de la campagne JDR Gaia 2 (personnage ZogZork). Source de verite du STATUT projet.

## Statut

- 2026-07-13 : **v2 LIVREE** - Toile (graphe de connectivite), recherche full-text, polices embarquees (hors-ligne parfait), hover-cards, nouveautes depuis la derniere session (dates git). Reste en v-plus-tard : champ relations: type (sur besoin). Review adversariale : 6 findings corriges.

- 2026-07-12 : **session 21 integree** (premier tour complet du process d'alimentation : photo + texte en vrac -> 127 fiches, 2 nouvelles affaires EN COURS, renommages La Vieille Garde / Eglise du Grand Ordonnateur, badges PJ/PNJ). Verifiee par contre-lecture agent. Points d'interpretation en attente de validation par Benoit (voir recap de conversation du 2026-07-12).
- 2026-07-11 : **v1 LIVREE** - build core (52 tests) + import complet (111 fiches) + review adversariale (25 findings corriges) + acceptation spec section 16 passee. EN ATTENTE : relecture du contenu par Benoit (l'import est fidele aux PDFs du 2026-07-10 ; ses souvenirs priment sur les PDFs).
- 2026-07-10 : spec de design validee -> `docs/2026-07-10-wiki-gaia2-spec.md` ; plan -> `docs/plans/2026-07-11-wiki-implementation.md`.

## Utilisation

- Consulter : double-clic sur `wiki.html` (complet) ; partager au MJ/joueurs : envoyer `wiki_partage.html` (sans fiches `prive: true` ni blocs `%%...%%`). JAMAIS wiki.html.
- Rebuild apres edition : `./publier.sh` = build + index.html (Pages) + copie vers `OneDrive/Gaia2-wiki/` (telephone hors-ligne). `python3 build_wiki.py` seul = build local sans publication. Le deploiement Pages part au commit+push.
- TELEPHONE (en session) : https://benam0u.github.io/gaia2-wiki/ -> Ajouter a l'ecran d'accueil. Hors-ligne : app OneDrive -> dossier Gaia2-wiki -> wiki.html (marquer "Toujours conserver sur cet appareil").
- REPO : `github.com/Benam0u/gaia2-wiki` (PUBLIC, assume - decision Benoit 2026-07-12) = TOUT le wiki : sources, docs, build, rendu, historique complet. Le nom `Gaia2` est reserve a l'editeur de fiches de personnage. L'ancien repo prive a ete renomme `gaia2-wiki-old-backup` (archive, supprimable a la main). Commit + push apres chaque mise a jour -> GitHub Pages redeploie index.html automatiquement.
- GARDE-FOU : un `%%` non ferme fait ECHOUER le build (fail-closed, rien n'est ecrit) - corriger la fiche indiquee puis relancer.
- `scripts/extract_systeme.py` : NE PAS relancer sans raison, il ecrase les fiches systeme (voir son en-tete).

## Alimentation - le process (valide 2026-07-11)

Un seul canal : ouvrir une session Claude dans `~/claude` (ou `Gaia2/`) et TOUT balancer en vrac dans un meme message, sans structurer. Quatre types d'entree, melangeables :

1. Photo(s) de notes manuscrites : glisser l'image dans le terminal (drag & drop) ou donner son chemin - Claude lit les notes sur la photo.
2. Texte tape/colle en vrac.
3. Corrections ("j'avais mal note, en fait c'est X", "nouveaute sur Y") - en langage naturel.
4. Etoffage ("developpe la fiche Ambroise avec ca").

Ce que Claude fait a chaque fois :

1. Session de jeu -> cree d'abord `sessions/session-NN.md` (deroule brut, template section 12).
2. Propage sur les fiches : creations, mises a jour, liens `[[...]]`, statuts. Les liens morts nouveaux sont normaux (fiches a creer plus tard, listees sur l'accueil).
3. Rebuild + rapport.
4. Recap de ce qui a change (fiches creees/modifiees + points ou il a du interpreter) -> relecture par Benoit (recap ou `git diff`), corrections, puis commit.

Conventions de dictee (optionnelles, sinon Claude choisit et le signale dans le recap) :
- "pas sur / je crois / peut-etre" -> marque hypothese (`statut:` ou `{?: ...}`).
- "note perso / prive" -> bloc `%%...%%` (exclu du partage).
- "a demander au MJ / a verifier" -> va dans `questions.md`.

Conventions editoriales (validees 2026-07-12) :
- Le wiki = les connaissances et la memoire DE ZOGZORK (in-character). Les evenements vecus a la table mais dont ZogZork n'a pas ete temoin sont VOLONTAIREMENT exclus, meme si Benoit les connait (ex. la punition exacte du Dr Hakim). Les autres joueurs peuvent le feuilleter, pas s'en servir activement.
- Benoit ecrit "Z" en dictant pour aller vite : JAMAIS cette abreviation dans les fiches, toujours ZogZork.
- Verification post-integration : fournir aux agents verificateurs le texte VERBATIM de Benoit (une transcription condensee genere des faux positifs).

Cas particuliers :
- Level-up : re-exporter le profil depuis le createur de fiche -> remplacer `data/zogzork_profile.json` (Claude strippe l'avatar) -> rebuild. La fiche technique (layout PDF depuis 2026-07-11) se regenere seule.
- Mode manuel toujours possible : editer les .md a la main puis `python3 build_wiki.py` ; demander a Claude une passe de coherence de temps en temps.

## Decisions cles

- Sessions nommees PAR DATE depuis le 2026-07-13 : `sessions/session-AAAA-MM-JJ.md`, titre `# Session du JJ/MM/AAAA` (l'ex session-21 = Session du 10/07/2026, alias conserve).
- Page Toile : graphe de connectivite des fiches (onglet dedie, filtres par type).

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
