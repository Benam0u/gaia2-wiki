# Wiki Gaia 2 - Spec de design

Validee par Benoit le 2026-07-10. Mise en prod : plus tard, sur demande (voir section 17).

## 1. Objet

Un wiki personnel de campagne pour Gaia 2 (personnage ZogZork, ~20 sessions de 9h) :

- des fiches d'entites croisees facon Wikipedia (personnages, lieux, factions, affaires, objets, creatures, concepts) avec references cliquables et backlinks automatiques ;
- un historique du deroule (chronologie du passe + journal de session pour le futur) ;
- alimente apres chaque session, soit par dictee a Claude, soit par edition manuelle des fichiers.

Le wiki capture la connaissance DU JOUEUR (ZogZork), pas la verite du MJ : les niveaux de confiance font partie du modele.

## 2. Decisions actees (2026-07-10)

- Consultation : PC en local (double-clic sur un fichier HTML) + partage possible au MJ/joueurs.
- Sortie : SINGLE-FILE. Un `wiki.html` autonome, navigation JS + hash routing, meme pattern que `Game/Horde/board.html`.
- Alimentation : mixte (dictee a Claude ET edition manuelle). Le format source doit rester simple a editer a la main.
- Donnees systeme (races, classes, competences, avantages) : section Systeme complete dans le wiki.
- Contenu prive : gere des la v1 (flag `prive` + blocs `%%...%%`), double sortie `wiki.html` (complet) + `wiki_partage.html` (filtre).
- Style graphique : design system exact de board.html (sombre chaud + accent or, Fraunces/Inter/JetBrains Mono).

## 3. Arborescence

```
Gaia2/
├─ Gaia2.md                  <- living doc du projet (statut, decisions)
├─ docs/                     <- specs et documents de design
├─ wiki/                     <- SOURCES (un .md par fiche)
│  ├─ personnages/           neros.md, van-richten.md, zogzork.md, petit-panda.md...
│  ├─ lieux/                 simpol.md, muscerie.md, taverne-ambroise.md...
│  ├─ factions/              la-garde.md, les-sauvages.md, empire-paxalpha.md...
│  ├─ affaires/              la-fleche.md, canas.md, fausse-epidemie.md...
│  ├─ objets/                carnet-de-neros.md, baies-de-loyaute.md...
│  ├─ creatures/             mere-des-monstres.md, bebou.md...
│  ├─ concepts/              technomagie.md, loi-beaute-moralite.md...
│  ├─ sessions/              _template.md, session-21.md, session-22.md...
│  ├─ chronologie.md         <- periodes reconstituees du passe
│  ├─ questions.md           <- questions ouvertes + a surveiller (affiche sur l'accueil)
│  ├─ img/                   <- portraits (races, classes, PNJ, avatar ZogZork)
│  └─ systeme/
│     ├─ races/              orc.md, mits.md... (20 fiches)
│     ├─ classes/            enqueteur.md, tavernier.md... (13 fiches)
│     ├─ competences.md      (table des 52 competences)
│     └─ avantages.md        (15 avantages generaux)
├─ data/
│  └─ zogzork_profile.json   <- copie du profil exporte (fiche technique, source de la partie generee)
├─ build_wiki.py             <- generateur (Python stdlib pur)
├─ wiki.html                 <- SORTIE complete (usage perso)
└─ wiki_partage.html         <- SORTIE filtree (MJ/joueurs)
```

Le dossier de type donne le type de la fiche (pas besoin de le repeter dans le frontmatter).

## 4. Format d'une fiche

En-tete YAML minimal + corps markdown libre. Exemple `affaires/la-fleche.md` :

```markdown
---
resume: Signature mysterieuse annoncant le cambriolage de Kretel
statut: confirme            # confirme | hypothese | fragment (defaut: confirme)
etat: en-cours              # affaires uniquement : en-cours | resolu | ferme
tags: [enquete, simpol]
alias: [Fleche]
decouverte: periode-affaires   # ou session-21 quand le journal existera
ne-pas-fusionner: [Canas, Baies de loyaute]   # affaires uniquement, optionnel
prive: false                # defaut: false
---

# La Fleche

Signature apposee sur un message annoncant le cambriolage de [[Kretel]].
[[Turdan]] etait sur sa piste avant d'etre tue accidentellement par [[ZogZork]].

%%Note perso : je soupconne que le MJ recycle le PNJ du sauna.%%

## Ce qu'on sait
...
```

Regles :

- Le titre de la fiche = le premier `# H1` du corps. C'est la cle de resolution des liens.
- Tous les champs du frontmatter sont optionnels sauf `resume` (une ligne, utilisee dans les index et la recherche).
- Champs supplementaires libres via `infobox:` (map cle-valeur affichee telle quelle dans l'infobox).
- `portrait: img/xxx.png` pour associer une image.
- Une fiche doit rester editable a la main en moins d'une minute : pas de champ obligatoire au-dela du resume.

## 5. Types d'entites

personnage (PNJ et PJ), lieu, faction, affaire, objet, creature, concept, session, race, classe. Les competences et avantages generaux vivent en tables dans deux fichiers uniques (pas une fiche par competence : trop de granularite pour rien).

Cas particulier ZogZork : la fiche `personnages/zogzork.md` contient le narratif (histoire, relations, style d'action) ecrit a la main, plus une directive `{{fiche_technique}}` que le build remplace par le rendu de `data/zogzork_profile.json` (attributs, PV/PF, degats, RD, competences, capacites, equipement, avatar). Apres un level-up : re-exporter le profil depuis le createur de fiche, remplacer le JSON, rebuild. Un fait, un endroit : le narratif dans le md, la technique dans le JSON.

## 6. Liens, alias, backlinks

- `[[Nom]]` ou `[[Nom|texte affiche]]` dans le corps. Resolution insensible a la casse et aux accents, sur le titre H1 puis sur les `alias`.
- Les alias servent aussi aux doutes de lecture (ex. Gretel vs Kretel : `alias: [Gretel]` sur la fiche Kretel tant que le doute n'est pas leve, ou deux fiches liees si le doute se confirme).
- Lien vers une fiche inexistante = LIEN MORT : affiche en rouille avec soulignement pointille, et liste sur l'accueil dans "Fiches a creer". C'est le moteur de croissance du wiki : on lie d'abord, on cree la fiche plus tard.
- Backlinks : calcules au build, affiches en bas de chaque fiche ("Mentionne dans : ..."). Jamais maintenus a la main.
- Le build signale aussi : alias en conflit (deux fiches revendiquent le meme nom), fiches orphelines (aucun backlink), blocs `%%` non fermes.

## 7. Niveaux de confiance et etats d'affaires

Reprend les conventions deja en place dans le dossier detaille :

- `statut: confirme` : pas de badge (le cas nominal).
- `statut: hypothese` : badge `? HYPOTHESE` en or. Pour les "le groupe soupconne...".
- `statut: fragment` : badge `~ FRAGMENT` en gris. Pour les notes brutes peu contextualisees (Tel, Knitt, Casper, Mick, Corien, Weed, pendentif carre...) conservees sans etre transformees en certitudes.
- Etats d'affaires : badge `EN COURS` (or), `RESOLU` (vert), `FERME` (gris) sur la fiche et dans les index.
- `ne-pas-fusionner` : affiche un avertissement en tete de fiche ("Ne pas fusionner avec X sans preuve en seance"). Le garde-fou anti-fusion du dossier devient une feature visible.

Le statut peut aussi s'appliquer inline dans le corps : `{?: Axelle serait Axxel}` rend le passage avec un marqueur hypothese. Optionnel, pour les fiches confirmees qui contiennent UNE phrase de speculation.

## 8. Contenu prive et double build

- `prive: true` dans le frontmatter : la fiche entiere est exclue de `wiki_partage.html` (contenu, entree d'index, resultats de recherche, backlinks).
- `%%...%%` dans un corps de fiche : le bloc est exclu du partage (et affiche sur fond legerement distinct dans la version complete, pour se rappeler que c'est prive).
- Dans le build partage, un `[[lien]]` vers une fiche privee est rendu en texte simple (pas en lien mort : ne pas teaser l'existence de la fiche).
- Un bloc `%%` non ferme fait ECHOUER le build (fail-closed, exit 2, aucune sortie ecrite) : rien n'est publie tant que la fiche n'est pas corrigee. Decision durcie post-review 2026-07-11 - c'est LE garde-fou de la confidentialite.
- Les deux fichiers sont generes a chaque build. Le partage = envoyer `wiki_partage.html` (Discord ou autre).

## 9. Chronologie a deux regimes

Le passe (~20 sessions) n'est pas reconstituable session par session, le dossier detaille le dit explicitement. Donc :

- PASSE : `wiki/chronologie.md` = les periodes nommees reconstituees (Expansion de Simpol -> Guerre -> Victoire et destructions -> Apres-guerre -> Prise de controle imperiale -> Montee des mouvements -> les affaires une a une), ordonnees par causalite, sans fausses dates.
- FUTUR : une fiche `sessions/session-NN.md` par seance a partir de la prochaine (numerotation demarree a 21, approximative et assumee ; ajustable). Template `_template.md` reprenant la section 12 du dossier : date reelle, presents, evenements, nouveaux personnages/lieux, indices, quetes ouvertes/fermees, consequences pour ZogZork, questions au MJ.
- La page Chronologie du wiki affiche les periodes puis la liste des sessions, bout a bout.
- `decouverte:` sur une fiche pointe la periode ou la session d'apparition, affiche dans l'infobox.

## 10. Pages generees dans wiki.html

Une seule page HTML, sections montrees/cachees par JS + hash routing (`#neros`, `#index-personnages`...), comme les panels du board.

- ACCUEIL = salle d'enquete : affaires EN COURS avec leur resume, puis le contenu de `wiki/questions.md` (fichier special a la racine de `wiki/` comme chronologie.md, deux sections : "Questions ouvertes" et "A surveiller a la prochaine partie"), derniere session, fiches a creer (liens morts), fiches recemment modifiees (mtime).
- INDEX PAR TYPE : table triable simple (nom, resume, statut/etat, tags) par categorie de la nav.
- FICHE ENTITE : titre, badges, infobox a droite (champs frontmatter + portrait), corps, avertissement anti-fusion le cas echeant, backlinks en bas.
- CHRONOLOGIE : periodes + sessions (section 9).
- SYSTEME : index races (20, avec portraits), index classes (13, avec portraits et les 10 avantages de classe chacune), table competences (52), avantages generaux (15). Fiche ZogZork enrichie par le JSON (section 5).
- TOILE (ajout 2026-07-13, ex-idee v2) : page graphe de connectivite - noeuds = fiches (couleur par type, taille = degre), aretes = wikilinks ; survol = voisins, clic = ouvre la fiche ; chips de filtrage par type (Sessions et Systeme off par defaut) ; canvas vanilla, zoom/pan souris et tactile.
- RECHERCHE : overlay Ctrl+K (et bouton loupe), navigation clavier. Full-text depuis 2026-07-12 : insensible aux accents, multi-mots (ET logique), cherche dans titre + alias + resume + tags ET dans le corps des fiches (textContent du DOM), resultats classes titre > meta > corps. Pas d'index externe.

## 11. Style graphique

Design system exact de board.html (source : bloc `<style>` du TEMPLATE de `Game/Horde/docs/build_board.py`) :

- Fonds : `--bg:#0E0F11`, `--surface:#15171B`, `--surface-2:#1C1F25`. Bordures : `--line:#2A2D34`, `--line-strong:#3A3E48`.
- Texte : `--text:#ECE7DA`, `--text-2:#9D968A`, `--text-3:#6A6660`.
- Accents : `--gold:#D4A85A` (liens, nav active, badges hypothese/en-cours), `--rust:#E25C3D` (liens morts, avertissements), `--green:#6FAE96` (resolu), `--blue:#7E9CC8` (dispo).
- Polices Google Fonts CDN : Fraunces (titres), Inter (corps), JetBrains Mono (nav, labels, badges). Fallbacks systeme propres si hors-ligne.
- Zero border-radius (sauf 3px code inline), zero box-shadow : la profondeur vient des bordures 1px et des surfaces.
- Header sticky avec blur, brand or en mono uppercase ("GAIA 2 - ARCHIVES DE ZOGZORK"), nav mono 11px uppercase avec soulignement or sur l'actif.
- Tables : th mono uppercase, hover or a 5%.

Adaptations wiki (nouvelles classes, meme grammaire visuelle) :

- Infobox : bloc flottant a droite, `--surface`, bordure `--line`, liseret gauche or 2px, labels mono uppercase `--text-3`.
- Badges de statut/etat : pattern `.st` du board (mono, petit, colore).
- Liens internes : or, soulignement discret ; liens morts : rouille pointille ; blocs prives : fond `--surface-2` + filet lateral `--text-3`.
- Overlay recherche : `--surface-2`, bordure `--line-strong`, comme le menu Archives du board.

## 12. build_wiki.py

Python stdlib pur (os, re, html, json, base64, datetime, unicodedata), zero dependance, comme build_board.py dont il reutilise le convertisseur markdown maison (headings, gras/italique, listes imbriquees, tables pipe, blockquotes, code) etendu de : wikilinks + alias, blocs `%%`, marqueur `{?:}`, directive `{{fiche_technique}}`.

Etapes du build :

1. Scanner `wiki/**/*.md`, parser frontmatter (parseur YAML minimal maison : cles plates, listes inline, pas de yaml lib) + H1.
2. Construire la table de resolution (titres + alias, normalises casse/accents) ; detecter les conflits.
3. Convertir chaque corps en HTML ; resoudre les wikilinks ; collecter les backlinks et les liens morts.
4. Rendre `data/zogzork_profile.json` dans la fiche ZogZork.
5. Generer index, accueil, chronologie ; embarquer les images en data URI.
6. Emettre `wiki.html` (tout) et `wiki_partage.html` (sans fiches `prive`, sans blocs `%%`, liens vers prive aplatis).
7. Afficher le rapport : N fiches, liens morts (liste), alias en conflit, orphelines, images manquantes. Un `%%` non ferme est fatal (voir section 8) : echec avant toute ecriture.

Contrainte de perf : build complet < 2 s, ouverture du wiki.html instantanee en `file://`.

Les images sont embarquees telles quelles : elles sont redimensionnees UNE FOIS a l'import (max ~512px, fait par Claude avec ses outils), pas par le build (stdlib ne sait pas redimensionner).

## 13. Import initial (a la mise en prod)

Sources et etapes :

1. Squelette : arborescence, build_wiki.py, template session, chronologie.
2. Entites campagne : generer ~60-80 fiches depuis le PDF "Gaia_2_Dossier_detaille_ZogZork_2026-07-10.pdf" (source principale, 12 pages) croise avec "Recap_Gaia_2_ZogZork_2026-07-10_v3.pdf". Reprendre fidelement les statuts (RESOLU/FERME/EN COURS), les hypotheses marquees, les fragments de la section 6.7, les separations a maintenir de la section 10.3.
3. Systeme : extraire `const characterData` (~ligne 3780 de `.../Projet_Weak_Auctions/JDR/index.html`, version canonique nettoyee) -> 20 fiches races + 13 fiches classes + competences.md + avantages.md ; copier et redimensionner les 33 portraits de `JDR/img/` (attention : `centaure.jpg` seul non-png, typo `avanturier.png`). Apres extraction, les md du wiki deviennent la copie de reference cote wiki ; le createur de fiche reste l'outil de creation, on ne le modifie pas.
4. ZogZork : copier `ZogZork_profile_level3_Juillet.json` vers `data/zogzork_profile.json` ; extraire l'avatar base64 en `wiki/img/zogzork.jpg` (redimensionne) ; rediger le narratif depuis les descriptions du JSON + le dossier.
5. Chronologie : les 13 periodes du dossier.
6. Relecture par Benoit : l'import est une passe de relecture pour lui, pas du travail de saisie. Corrections de memoire, puis premiere session live.

Inventaire attendu (repere pour verifier la completude de l'import) : ~26 PNJ + 6 PJ, ~10 lieux, ~8 factions, 6 affaires + fragments, ~9 objets, ~9 creatures, ~10 concepts, ~13 questions ouvertes, 13 periodes. Verite = le contenu des PDFs au moment de l'import.

## 14. Workflow post-session

Mode dictee (principal) :

1. Benoit colle ses notes en vrac (ou dicte) dans une conversation Claude.
2. Claude cree `sessions/session-NN.md`, met a jour les fiches touchees (nouveaux faits, changements de statut, nouvelles fiches, liens), rebuild.
3. Benoit relit le diff git et corrige.

Mode manuel : Benoit edite les .md, lance `python3 build_wiki.py`, commit.

`Gaia2/` est un repo git : historique complet de l'evolution des connaissances, diff entre sessions, et rollback si une session introduit des erreurs.

## 15. v2 et non-goals

Idees notees, PAS dans la v1 - etat au 2026-07-13 :

- FAIT (v2) : mini-cartes au survol des liens (titre + type + resume + portrait, desktop).
- FAIT (v2) : graphe de relations visuel = la page Toile.
- FAIT (v2) : polices embarquees en base64 (assets/fonts.css, dedupliquees par famille/subset) - rendu identique 100% hors-ligne, zero CDN.
- FAIT (v2) : nouveautes depuis la derniere session (dates git avec suivi des renames, bloc accueil + point dore dans les index) ; Recemment modifiees passe aussi sur les dates git.
- FAIT (2026-07-13) : champ `relations:` type dans le frontmatter - map indentee `Libelle: "[[Cible]]"` (valeurs TOUJOURS entre guillemets). Affiche dans l'infobox cote source, agrege automatiquement cote cible (bloc "Relations : Source (Libelle)"), compte comme lien (backlinks + aretes de la Toile). La liste v2 est donc entierement livree.

Non-goals : moteur wiki serveur, editeur in-browser, hebergement, multi-utilisateurs, donnees du MJ.

## 16. Criteres d'acceptation v1

- `python3 build_wiki.py` genere les deux HTML en < 2 s avec le rapport de coherence.
- Double-clic sur wiki.html en `file://` : tout fonctionne (nav, hash, recherche Ctrl+K, images) sans reseau (hors polices).
- Chaque `[[lien]]` du corpus resout ou apparait comme lien mort liste sur l'accueil.
- Les backlinks de 3 fiches prises au hasard sont exacts.
- `wiki_partage.html` ne contient aucune fiche privee ni bloc `%%` (verification grep sur le HTML genere).
- La fiche ZogZork affiche la fiche technique issue du JSON, fidele au PDF de la fiche de personnage.
- Le look est indistinguable du board (verification visuelle par Benoit).

## 17. Plan de mise en prod (a lancer quand Benoit le decide)

1. Build core : build_wiki.py + template + style, valide sur 3-4 fiches de test.
2. Import campagne + systeme + ZogZork (section 13). Gros du travail, parallelisable par type de fiche.
3. Relecture Benoit + corrections.
4. Premiere session live (session 21) en mode dictee.

Prochaine etape cote process : plan d'implementation detaille (skill writing-plans) au moment de la mise en prod.
