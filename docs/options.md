# Options actuelles

## Modes

- **Navigation (browser)**: affiche dossiers, fichiers zip et images du repertoire courant.
- **Diaporama (slideshow)**: affiche les images en plein cadre adapte a la fenetre.
- **Galerie miniatures**: sous-vue du diaporama, grille defilante avec vignettes de toutes les images de la source courante.

## Commandes clavier

### Navigation

- `Up` / `Down`: deplacer la selection.
- `Right` ou `Enter`: ouvrir un dossier, un zip, ou lancer le diaporama d'une image (hors **mode tri**, voir section dediee).
- `Left` ou `Backspace`: revenir au dossier parent.
- `Esc`: quitter l'application (sauf en mode tri: quitter uniquement le mode tri).
- `d` (liste active): activer le **mode tri** (deplacer / copier des fichiers vers un autre dossier).

### Mode tri (deplacement / copie, navigation)

Active avec `d` lorsque le focus est sur la liste du navigateur. Un panneau rappelle les raccourcis.

- `d`: cible **zip et dossiers** (sources de type dossier ou fichier `.zip`).
- `i`: cible **images** (fichiers avec extension image).
- `m` / `c`: operation **deplacer** ou **copier** (si la source ne permet pas le deplacement, la copie est utilisee).
- `0` a `9` ou pave `KP_0`..`KP_9`: aller au dossier enregistre dans `config/settings.json` (`folder_shortcuts`).
- `Ctrl` + `Shift` + chiffre (ligne `0`–`9` ou pave `KP_0`..`KP_9`): enregistrer le dossier courant pour ce chiffre.
- `Right`: entrer dans un dossier, ou ouvrir zip / image (quitte le mode tri si vous lancez le diaporama).
- `Enter`: sur un **dossier destination**, premiere pression arme la confirmation, seconde sur le meme dossier ouvre le dialogue Oui/Non puis execution. Pas d'ouverture de dossier avec `Enter` dans ce mode (utiliser `Right`).
- Si un fichier ou dossier du meme nom existe deja dans la destination, un dialogue propose **Renommer** (suffixe `_1`, `_2`, etc.), **Ecraser** ou **Annuler** (fermeture de la fenetre = annuler).
- `u`: annuler la destination armee.
- `r`: previsualiser la regle de tri auto (dry-run) puis proposer l'execution.
- `Esc`: quitter le mode tri sans quitter l'application.

Les conflits de nom sur la destination sont regles via le dialogue (renommer avec suffixe `_1`, `_2`, etc., ou ecraser).

### Diaporama (vue image plein ecran)

- `Left`: image precedente, ou fermeture du diaporama si on est deja sur la premiere image.
- `Right`: image suivante, ou fermeture du diaporama si on est deja sur la derniere image.
- `Up`: aller directement a la premiere image.
- `Down`: aller directement a la derniere image.
- `Page_Up` (`Prior`): ouvrir la galerie miniatures.
- `Page_Down` (`Next`): sans effet (reserve au retour depuis la galerie).
- `Esc`: retour au mode navigation.
- `Space`: activer/desactiver l'autoplay.
- `+` / `KP_Add`: accelerer l'autoplay (pas de 250 ms, min 250 ms).
- `-` / `KP_Subtract`: ralentir l'autoplay (pas de 250 ms, max 20000 ms).
- `?`: afficher l'aide du diaporama avec les commandes et les informations de l'image courante.
- `g` / `j` / `t`: etiqueter l'image courante (`garder`, `jeter`, `a_trier`) pour le mode review.
- `e`: exporter les etiquettes review dans `logs/review_labels.json` et `logs/review_labels.csv`.

### Galerie miniatures (depuis le diaporama)

- `Page_Up`: defiler la page vers le haut dans la grille.
- `Page_Down` ou `Enter`: afficher en plein ecran la vignette selectionnee (met a jour l'index courant).
- `Esc`: fermer la galerie sans appliquer la selection (restaure l'index d'ouverture de la galerie).
- Fleches: deplacer la selection (ordre row-major dans la grille).
- `+` / `-`: augmenter ou diminuer le niveau de taille des vignettes (1 a 9), enregistre dans la configuration.
- `*` (`KP_Multiply` ou `Shift+8` sur clavier US): revenir au niveau de taille par defaut.

## Comportements

- Les images supportees sont: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`.
- Les archives `.zip` sont traitees comme des sources d'images.
- Les images illisibles/corrompues sont sautees avec message de statut.
- Le diaporama propose une aide overlay avec le nom, le chemin, la taille et le type de source de l'image courante.
- Si l'aide est ouverte, la commande suivante la ferme sans executer l'action associee.
- Les commandes de navigation du diaporama (`Left`, `Right`, `Up`, `Down`) sont limitees a 3 inputs en attente; les suivantes sont ignorees tant que la file est pleine.
- A la fin du diaporama, l'app revient automatiquement au mode navigation dans le dossier conteneur.
- A la sortie d'un zip, le handle est ferme (pas de conservation memoire du zip ouvert).
- La fenetre demarre avec une taille initiale adaptee a l'ecran.
- Les preferences utilisateur (niveau de taille des vignettes, raccourcis dossiers `folder_shortcuts`) sont lues et ecrites dans `config/settings.json` sous le repertoire de travail courant (`Path.cwd()`). Un fichier d'exemple versionne est fourni : `config/settings.example.json`.
- Un onboarding court est affiche au premier lancement (flag `onboarding_done` dans les settings).
- Les hotkeys critiques de tri sont personnalisables via `Ctrl+K` (mapping `hotkeys` dans les settings).
- Les regles de tri auto sont stockees dans `sorting_rules` (conditions simples `ext`, `name_contains`, destination).
- Les journaux applicatifs sont ecrits par defaut dans `logs/image_viewer.log` (repertoire de travail courant). Les dossiers `logs/` et le fichier `config/settings.json` sont ignores par git (voir `.gitignore`).

## Validation UX par lot

- **Lot 1**: verifier bandeau de mode + hint contextuel + toast apres operation tri.
- **Lot 2**: verifier highlights source/pending en mode tri, filtre navigateur, affichage journal (`l`).
- **Lot 3**: verifier onboarding premier lancement et edition des hotkeys (`Ctrl+K`) persistante.
- **Lot 4**: verifier regle auto (`r`) en dry-run + execution, review `g/j/t` + export `e`.

## Lancement

- `python -m image_viewer [chemin_optionnel]`
- `image-viewer [chemin_optionnel]` (apres installation du projet)
- `./scripts/run_ubuntu.sh [chemin_optionnel]`

## Historique des options

- **v0.1.0**
  - Packaging standard `pyproject.toml` + package `image_viewer`.
  - Point d'entree `python -m image_viewer` et commande `image-viewer`.
  - Script Ubuntu `scripts/run_ubuntu.sh`.
- **v0.2.0**
  - Decoupage de la logique en modules `sources` et `slideshow`.
  - Ajout de `Up` / `Down` dans le diaporama et fermeture sur `Left` depuis la premiere image.
  - Ajout d'une aide `?` avec informations sur l'image courante.
  - Limitation de la file des inputs de navigation a 3 actions.
- **v0.3.0**
  - Galerie miniatures dans le diaporama (`Page_Up` pour ouvrir, `Page_Down` / `Enter` pour valider, `Esc` pour annuler).
  - Persistance JSON `config/settings.json` (niveau de taille des vignettes).
  - Journalisation fichier `logs/image_viewer.log` et `.gitignore` racine.
- **v0.4.0**
  - Mode tri (`d`) dans le navigateur: deplacement / copie vers un dossier, raccourcis dossiers `0`–`9`, panneau d'aide integre.
