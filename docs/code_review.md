# Review technique de `src/app.py` (version initiale)

## Niveau critique

- Aucun bug bloquant evident dans le flux principal dossier/zip/navigation.

## Niveau eleve

- **Architecture monolithique**: la quasi-totalite de la logique (UI, navigation, gestion de sources, demarrage) est dans un seul module, ce qui ralentit l'evolution et la testabilite.
- **Couplage UI/logique**: les fonctions de lecture d'images et de gestion d'erreurs ecrivent directement l'etat UI (`_set_status`), compliquant des tests unitaires non-GUI.

## Niveau moyen

- **Gestion des erreurs heterogene**: certains chemins remontent `SourceError`, d'autres absorbent les exceptions generiques; le comportement utilisateur est robuste mais difficile a verifier automatiquement.
- **Signaux de dette dans le code**: presence de commentaires de travail in-line ("Dans __init__ de App..."), imports inutilises, et absence de structure package.
- **Point d'entree unique non package**: execution basee sur `src/app.py`, moins standard pour distribution et scripts d'installation.

## Niveau faible

- **Messages UI et conventions melanges**: accents/typographie variables dans les statuts, sans impact fonctionnel.

## Quick wins appliques pendant ce chantier

- Refactor vers un package Python `image_viewer` avec point d'entree standard `python -m image_viewer`.
- Ajout d'un script de lancement Ubuntu idempotent.
- Clarification du point d'entree via `run_with_error_boundary()`.
- Correction defensive: annulation explicite d'autoplay dans `_close_slideshow()` pour eviter un timer residuel lors des transitions.

## Recommandations pour les iterations suivantes

- Extraire une couche "service" pure pour les sources (`FolderSource`, `ZipSource`) et un controleur testable sans Tk.
- Ajouter des tests unitaires sur la logique de navigation (index, fin de slideshow, saut d'images corrompues).
- Ajouter une CLI explicite (`argparse`) pour des options futures (autoplay initial, delai, filtres d'extensions).
