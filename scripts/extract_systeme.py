#!/usr/bin/env python3
"""Extraction de la section Systeme du wiki Gaia 2.

Source de verite : `const characterData = {...}` dans le createur de fiche
(JDR/index.html, ~ligne 3780). Ce script est REJOUABLE : il regenere les
fiches races/classes/competences/avantages et reimporte les images.

ATTENTION : rejouer ce script ECRASE les fiches wiki/systeme/ (y compris les
editions manuelles faites apres l'import initial du 2026-07-11, ex. les alias
ajoutes sur mits.md). Ne le relancer que si le createur de fiche change, et
re-appliquer les editions wiki ensuite (git diff est ton ami).
Les images sont toutes converties en JPEG (fond #0E0F11 sous la transparence).

Sorties :
  wiki/systeme/races/<id>.md      (20 fiches)
  wiki/systeme/classes/<id>.md    (13 fiches)
  wiki/systeme/competences.md     (table des 52 competences)
  wiki/systeme/avantages.md       (15 avantages generaux + table levelUps)
  wiki/img/races/*, wiki/img/classes/*  (33 images, max 512px de large)
"""

import json
import os
import re
import shutil
import sys

SOURCE_HTML = "/mnt/c/Users/benoi/OneDrive/Bureau/Dev/WeakAuction/project_cursor/Projet_Weak_Auctions/JDR/index.html"
SOURCE_IMG = "/mnt/c/Users/benoi/OneDrive/Bureau/Dev/WeakAuction/project_cursor/Projet_Weak_Auctions/JDR/img"
WIKI_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wiki")
MAX_WIDTH = 512

# La race et la classe de ZogZork recoivent un lien vers sa fiche.
ZOGZORK_RACE = "orc"
ZOGZORK_CLASSE = "enqueteur"

# Typo dans les assets du createur : l'image de la classe Aventurier
# (id "avanturier") s'appelle avanturier.png ; le wiki la renomme.
IMG_RENAME = {"avanturier.png": "aventurier.png"}


def extract_character_data(path):
    """Localise `const characterData = {...}` et le parse en dict."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"const characterData\s*=\s*", src)
    if not m:
        sys.exit("ERREUR : `const characterData =` introuvable dans " + path)
    start = m.end()
    depth = 0
    end = None
    in_str = False
    esc = False
    for j in range(start, len(src)):
        c = src[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = j
                break
    if end is None:
        sys.exit("ERREUR : accolades non equilibrees apres characterData")
    blob = src[start:end + 1]
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        # Fallback : virgules trainantes avant } ou ]
        blob = re.sub(r",\s*([}\]])", r"\1", blob)
        return json.loads(blob)


def verify(data):
    checks = [
        ("races", 20, len(data.get("races", []))),
        ("classes", 13, len(data.get("classes", []))),
        ("competences", 52, len(data.get("competences", []))),
        ("avantagesGeneraux", 15, len(data.get("avantagesGeneraux", []))),
    ]
    ok = True
    for name, expected, got in checks:
        status = "OK" if got == expected else "ECHEC"
        if got != expected:
            ok = False
        print(f"  {name}: {got} (attendu {expected}) {status}")
    if "levelUps" not in data:
        print("  levelUps: ABSENT ECHEC")
        ok = False
    else:
        print(f"  levelUps: present ({len(data['levelUps'])} paliers) OK")
    if not ok:
        sys.exit("ERREUR : verification des comptes echouee, abandon.")


def sanitize(text):
    """Une ligne propre : pas de tiret cadratin, espaces normalises."""
    return re.sub(r"\s+", " ", text.replace("—", "-")).strip()


def first_sentence(text):
    """Premiere phrase de la description, pour le resume."""
    text = sanitize(text)
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    return (m.group(1) if m else text).rstrip(".")


def split_trait(trait):
    """'Nom : effet' -> '**Nom** - effet' ; sinon la chaine telle quelle."""
    trait = sanitize(trait)
    if " : " in trait:
        name, effect = trait.split(" : ", 1)
        return f"**{name}** - {effect}"
    return trait


def write_fiche(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("  ecrit", os.path.relpath(path, os.path.join(WIKI_ROOT, "..")))


def gen_races(races):
    for race in races:
        rid = race["id"]
        ext = "jpg"
        desc = sanitize(race["description"])
        lines = [
            "---",
            f"resume: {first_sentence(race['description'])}",
            "tags: [race]",
            f"portrait: img/races/{rid}.{ext}",
            "---",
            "",
            f"# {race['name']}",
            "",
            desc,
        ]
        if rid == ZOGZORK_RACE:
            lines += ["", "C'est la race de [[ZogZork]]."]
        lines += ["", "## Bonus", ""]
        lines += [f"- {split_trait(b)}" for b in race["bonuses"]]
        lines += ["", "## Malus", ""]
        lines += [f"- {split_trait(m)}" for m in race["maluses"]]
        write_fiche(os.path.join(WIKI_ROOT, "systeme", "races", rid + ".md"), lines)


def gen_classes(classes):
    for cls in classes:
        cid = cls["id"]
        img_name = IMG_RENAME.get(cid + ".png", cid + ".png").rsplit(".", 1)[0] + ".jpg"
        desc = sanitize(cls["description"])
        lines = [
            "---",
            f"resume: {first_sentence(cls['description'])}",
            "tags: [classe]",
            f"portrait: img/classes/{img_name}",
            "---",
            "",
            f"# {cls['name']}",
            "",
            desc,
        ]
        if cid == ZOGZORK_CLASSE:
            lines += ["", "C'est la classe de [[ZogZork]]."]
        lines += ["", "## Avantages de classe", ""]
        for av in cls["avantages"]:
            lines.append(f"- **{sanitize(av['name'])}** - {sanitize(av['description'])}")
        write_fiche(os.path.join(WIKI_ROOT, "systeme", "classes", cid + ".md"), lines)


def gen_competences(competences):
    lines = [
        "---",
        "resume: Table des 52 compétences du système et leur attribut associé",
        "tags: [systeme]",
        "---",
        "",
        "# Compétences",
        "",
        f"Les {len(competences)} compétences du système, avec l'attribut sur lequel chacune repose.",
        "",
        "| Nom | Attribut |",
        "| --- | --- |",
    ]
    for comp in competences:
        lines.append(f"| {sanitize(comp['name'])} | {sanitize(comp['attribut'])} |")
    write_fiche(os.path.join(WIKI_ROOT, "systeme", "competences.md"), lines)


def gen_avantages(avantages, level_ups):
    lines = [
        "---",
        "resume: Les 15 avantages généraux disponibles à la création, et les options de montée de niveau",
        "tags: [systeme]",
        "---",
        "",
        "# Avantages généraux",
        "",
        f"Les {len(avantages)} avantages généraux disponibles à la création de personnage.",
        "",
    ]
    for av in avantages:
        lines.append(f"- **{sanitize(av['name'])}** - {sanitize(av['description'])}")
    lines += [
        "",
        "## Montée de niveau",
        "",
        "Options offertes à chaque passage de niveau (une au choix).",
        "",
        "| Niveau | Options |",
        "| --- | --- |",
    ]
    for lu in level_ups:
        opts = ", ".join(sanitize(o["name"]) for o in lu["options"])
        lines.append(f"| {lu['level']} | {opts} |")
    write_fiche(os.path.join(WIKI_ROOT, "systeme", "avantages.md"), lines)


def import_images():
    try:
        from PIL import Image
        have_pil = True
    except ImportError:
        have_pil = False
        print("  Pillow indisponible : copie simple sans redimensionnement")

    count = 0
    for sub in ("races", "classes"):
        src_dir = os.path.join(SOURCE_IMG, sub)
        dst_dir = os.path.join(WIKI_ROOT, "img", sub)
        os.makedirs(dst_dir, exist_ok=True)
        for name in sorted(os.listdir(src_dir)):
            if not name.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            dst_name = IMG_RENAME.get(name, name).rsplit(".", 1)[0] + ".jpg"
            src = os.path.join(src_dir, name)
            dst = os.path.join(dst_dir, dst_name)
            if have_pil:
                img = Image.open(src)
                if img.width > MAX_WIDTH:
                    h = round(img.height * MAX_WIDTH / img.width)
                    img = img.resize((MAX_WIDTH, h), Image.LANCZOS)
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGBA")
                    bg = Image.new("RGB", img.size, (14, 15, 17))
                    bg.paste(img, mask=img.split()[-1])
                    img = bg
                else:
                    img = img.convert("RGB")
                img.save(dst, "JPEG", quality=82, optimize=True)
            else:
                shutil.copy2(src, dst)
            count += 1
    print(f"  {count} images importees (attendu 33)", "OK" if count == 33 else "ECHEC")
    if count != 33:
        sys.exit("ERREUR : nombre d'images inattendu")


def main():
    print("Extraction de characterData...")
    data = extract_character_data(SOURCE_HTML)
    print("Verification des comptes :")
    verify(data)
    print("Generation des fiches :")
    gen_races(data["races"])
    gen_classes(data["classes"])
    gen_competences(data["competences"])
    gen_avantages(data["avantagesGeneraux"], data["levelUps"])
    print("Import des images :")
    import_images()
    print("Termine.")


if __name__ == "__main__":
    main()
