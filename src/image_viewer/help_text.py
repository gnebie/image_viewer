"""Static help text shown by the ? overlay."""

HELP_TEXT = """Commandes

Navigation
  Up / Down      selection
  Right / Enter  ouvrir dossier, zip, image
  Left           dossier parent
  Backspace      dossier parent
  Home / End     premier / dernier element
  Esc            quitter (navigation) ; quitter mode tri (mode tri)
  d              mode tri (deplacement / copie)
  ?              aide (toutes les commandes)

Diaporama
  Left           image precedente (ou fermer au debut)
  Right          image suivante (ou fermer a la fin)
  Up             premiere image
  Down           derniere image
  Page_Up        galerie miniatures (depuis l'image)
  Page_Down      (image) sans effet ; (galerie) ouvrir l'image selectionnee
  Space          autoplay on/off
  + / -          vitesse autoplay (image) ; taille vignettes (galerie)
  *              taille vignettes par defaut (galerie)
  ?              aide
  Esc            retour navigation (image) ; annuler galerie (galerie)

Galerie miniatures
  Fleches        deplacer la selection
  Page_Up        defiler la page vers le haut
  Entree         ouvrir l'image selectionnee
  Esc            fermer sans appliquer la selection

Mode tri (navigation, focus listbox)
  d              activer le mode ; cible zip/dossier (d) ou images (i)
  i              cible images
  m / c          deplacer / copier
  r              appliquer une regle auto (dry-run puis confirmation)
  u              annuler destination armee
  0-9            aller au raccourci dossier (config)
  Ctrl+Shift+chiffre  enregistrer le dossier courant pour ce chiffre (ligne ou pave)
  Entree         sur dossier: armer puis confirmer (2 fois) puis dialogue
  Right          entrer dossier ou ouvrir zip / image
  Esc            quitter le mode tri

Divers
  f              plein ecran on/off
  l              afficher/masquer le journal des operations (navigation)
  Ctrl+K         configurer les hotkeys
  g / j / t      etiqueter image courante (garder/jeter/a_trier) en diaporama
  e              exporter les etiquettes review (json+csv)
  r              en mode tri: appliquer une regle auto (dry-run + confirmation)
  F5             recharger le dossier courant (navigation)
"""
