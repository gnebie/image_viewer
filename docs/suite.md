## suite 1
Ensuite je veux pouvoir avoir un systeme qui me permet de faire l'autre usage de l'image viewer qui est de trier les images / zip 
pour cela je doit avoir un mode me permettant de deplacer les images ou les zip plus facilement.

Je veux pouvoir entrer dans un mode deplacement sur la touche 'd'
Ensuite dans ce mode j'aurais plusieurs options:
l'option zip est par defaut mais si j'appuie sur 'i' je passe en mode image.  et si on appuie sur 'd' on passe en zip/dossier.

Par defaut on est en move mais si on appuie sur 'c' on passe en copie. et si on appuie sur 'm' on repasse en move(l'option move n'etant pas accessible sur une image en zip elle ne doit pas etre autorisee)

On doit pouvoir se deplacer entre les dossiers comme dans le mode galerie et appuier sur entree pour deplacer (ou copier) dans le dossier. il doit y avoir une popup pour demander si on est sur preselectionnee sur ok pour pouvoir simplement double entree

Il doit dans le fichier de config des preferences de l'utilisateur avoir la possibilite de specifier des raccourcis de dossiers pour etre plus simple a utiliser.
Les racourcis pourront etre mis sur les touches de chiffres (1234567890) on peut en avoir 10 max. 
Pour cree un raccourci a partir du menu de deplacement il faudra fait 'shift' + le chiffre

Dans le menu des deplacement il doit y avoir un petit panneau pour rappeller les differentes options de ce mode.

## suite 2

Fait une review complete du code pour voir ce qui peut etre ameliorer 

Fait en une liste d'ameliorations a faire, avec des points que je validerai avant de te laisser les faire ou de les enlever

## suite 3 

Fait une analyse de l'ux, de l'experience utilisateur.
Et fait une liste de propositions pour ameliorer la partie ux du projet 

Fait aussi une liste des options qui seraient interessantes pour ce projet. 

Fait en une liste d'ameliorations a faire, avec des points que je validerai avant de te les donner

### Analyse UX complete (etat actuel)

#### Forces actuelles
- Le produit est tres **clavier-first** et rapide pour un usage expert (navigation, tri, galerie, diaporama).
- Le flux principal reste simple: navigateur dossier -> image/zip -> diaporama -> retour.
- Le mode tri est deja securise (double validation + gestion de conflits de nom).
- Les raccourcis dossiers persistants sont une excellente base pour le tri intensif.

#### Frictions UX majeures
- **Charge cognitive elevee**: beaucoup de raccourcis, repartis sur plusieurs modes, sans onboarding progressif.
- **Discoverability limitee**: certaines actions importantes (Page_Up, Page_Down, Ctrl+Shift+chiffres) ne sont pas evidentes au premier usage.
- **Ambiguite des touches selon le mode**: meme touche, comportement different (ex: `Esc`, `Enter`, `Page_Down`).
- **Feedback visuel faible** en mode navigateur/tri: la source, la cible et l'etat "arme" reposent surtout sur la barre de statut.

#### Frictions UX secondaires
- Le statut est informatif, mais ephemere; pas d'historique des dernieres operations.
- Pas de distinction visuelle forte entre "navigation normale" et "mode tri actif" hors panneau texte.
- L'aide `?` est riche en diaporama mais absente en mode navigateur/tri.
- Le comportement de scroll/saut en galerie est efficace, mais peut sembler "opaque" sur gros corpus (placeholders, chargement progressif).

### Propositions UX (existant) - priorisees

#### Quick wins (impact fort, effort S/M)
1. **Bandeau mode persistant** en haut (`Navigation` / `Tri: image|zip` / `Diaporama` / `Galerie`).
   - Impact: forte reduction des erreurs de mode.
   - Effort: S.
2. **Aide contextuelle courte inline** (1 ligne) selon le mode, sans ouvrir l'overlay.
   - Impact: meilleure memorisation des commandes critiques.
   - Effort: S.
3. **Confirmation explicite post-action tri** (ex: "Deplace vers X", "Copie + renommage _1").
   - Impact: confiance utilisateur accrue.
   - Effort: S.
4. **Signal visuel de source tri** (highlight dedie de l'element source).
   - Impact: baisse des deplacements errones.
   - Effort: M.
5. **Commande d'annulation rapide de l'armement** (ex: `Backspace` ou `u`) en mode tri.
   - Impact: fluidite lors des fausses manipulations.
   - Effort: S.

#### Chantiers structurels (impact fort, effort M/L)
1. **Palette de commandes (`Ctrl+K`)** listant actions + raccourcis.
2. **Personnalisation des raccourcis clavier** (mapping utilisateur, pas uniquement fixe).
3. **Journal des operations tri** (10-20 dernieres actions) avec possibilite d'annulation pour copies/deplacements simples.
4. **Assistant d'onboarding premier lancement** (2-3 ecrans max: navigation, tri, galerie).

### Options interessantes pour le projet (roadmap)

#### Valeur immediate (court terme)
- **Filtres rapides** dans le navigateur (images seulement, zips seulement, recherche par nom).
- **Tags/favoris dossiers** (au-dela des 10 raccourcis numeriques).
- **Mode "review rapide"**: marquer image comme garder/jeter/a-trier sans quitter le flux clavier.
- **Affichage metadata photo** (EXIF de base) dans l'aide image.

#### Valeur differenciante (moyen terme)
- **Tri assiste par regles**: destination auto selon pattern de nom, date, dimensions, extension.
- **Comparaison cote-a-cote** de 2 images en diaporama.
- **Collections virtuelles** (playlists d'images multi-dossiers/zips) sans deplacement physique.
- **Batch rename** integre avec preview.

#### Valeur avancee (long terme)
- **Plugin hooks** (pre/post move/copy) pour workflows perso.
- **Indexation locale** pour recherche ultra-rapide sur gros volumes.
- **Profil d'usage** (photographie, archivage, tri technique) avec presets de raccourcis/UI.

### Liste d'ameliorations a valider avant implementation

Format: `ID | Probleme | Proposition | Impact | Effort | Validation requise`

1. `UX-01 | Confusion de mode | Bandeau de mode persistant + couleur distincte | Fort | S | Valider wording et style`
2. `UX-02 | Trop de commandes a memoriser | Hint contextuel 1 ligne selon mode | Fort | S | Valider contenu des hints`
3. `UX-03 | Erreurs de tri possibles | Highlight visuel source + cible + etat arme | Fort | M | Valider design de mise en evidence`
4. `UX-04 | Feedback tri vite oublie | Toasts de confirmation (copie/move/rename/overwrite) | Moyen | S | Valider niveau de detail`
5. `UX-05 | Recuperation apres erreur faible | Mini journal des operations recentes | Fort | M | Valider portee (affichage seul vs undo)`
6. `UX-06 | Apprentissage initial abrupt | Onboarding court premier lancement | Moyen | M | Valider parcours (2 ou 3 etapes)`
7. `UX-07 | Navigation dossier limitee | Recherche/filtre instantane dans liste browser | Fort | M | Valider UX (champ permanent ou toggle)`
8. `UX-08 | Raccourcis rigides | Ecran de personnalisation des touches | Fort | L | Valider priorites (quelles touches configurables)`
9. `UX-09 | Tri repetitif manuel | Regles de tri automatiques basiques | Fort | L | Valider syntaxe des regles`
10. `UX-10 | Vision produit court terme | Mode review garder/jeter/a-trier | Moyen | M | Valider logique metier de classification`

### Proposition d'ordre de mise en oeuvre (si tu valides)
- **Lot 1 (rapide)**: UX-01, UX-02, UX-04
- **Lot 2 (fiabilite tri)**: UX-03, UX-05, UX-07
- **Lot 3 (produit)**: UX-06, UX-08
- **Lot 4 (avance)**: UX-09, UX-10

## suite 4

Regarde ce qu'il manque pour faire un repo git public propre.

