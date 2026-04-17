# image_viewer

[![CI](https://github.com/gnebie/image_viewer/actions/workflows/ci.yml/badge.svg)](https://github.com/gnebie/image_viewer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Outil desktop Python (Tkinter + Pillow) pour parcourir des dossiers d'images, ouvrir des archives zip d'images et trier rapidement via navigation clavier.

Le code est maintenant separe entre l'UI Tkinter et la logique metier principale:
- `src/image_viewer/app.py`: fenetre, widgets, bindings et rendu.
- `src/image_viewer/sources.py`: acces aux dossiers, zips et descriptions d'images.
- `src/image_viewer/slideshow.py`: etat du diaporama, navigation et file d'inputs bornee.

## Features

- Navigation clavier rapide dossier/zip/image.
- Diaporama + galerie de miniatures.
- Mode tri move/copy avec confirmations et gestion des conflits de nom.
- Raccourcis dossiers persistants.
- Raccourcis/hotkeys configurables et onboarding premier lancement.
- Review labels (`g/j/t`) + export JSON/CSV.

## Prerequis

- Python 3.12+
- Ubuntu/Debian: `python3-venv` et `python3-tk` installes

Exemple:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-tk
```

## Lancement rapide (Ubuntu)

```bash
./scripts/run_ubuntu.sh
```

Avec un chemin de depart:

```bash
./scripts/run_ubuntu.sh /chemin/vers/dossier_ou_zip_ou_image
```

Le script:
- cree `.venv` si necessaire,
- installe les dependances et le projet,
- lance l'application et reste actif tant que l'app tourne.

## Lancement manuel

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m image_viewer
```

## Documentation

- Options detaillees: [`docs/options.md`](docs/options.md)
- Revue technique du code initial: [`docs/code_review.md`](docs/code_review.md)
- Changelog: [`CHANGELOG.md`](CHANGELOG.md)
- Contribution: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Securite: [`SECURITY.md`](SECURITY.md)

## Roadmap

- Stabilisation UX et lisibilite des modes.
- Amelioration des workflows de tri automatique.
- Qualite de release et documentation publique.

## Limitations

- L'UI repose sur Tkinter (environnement desktop requis).
- Certaines distributions Linux necessitent `python3-tk` installe explicitement.
- Les tests slideshow qui touchent PIL/Tk peuvent etre dependants de l'environnement.

## FAQ

### Peut-on lancer sans script Ubuntu ?
Oui, via venv + `pip install -e .` puis `python -m image_viewer`.

## Licence

Projet sous licence MIT. Voir [`LICENSE`](LICENSE).

## Nouveautes recentes

- `Up` et `Down` en diaporama pour aller directement au debut ou a la fin.
- `Left` ferme le diaporama si tu es deja sur la premiere image.
- `?` ouvre une aide avec les commandes et les informations de l'image courante.
- Les inputs de navigation en diaporama sont limites a 3 actions en attente.
