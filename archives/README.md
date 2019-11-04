# Archives

## Fichiers
- midori[commit=d2e74dcd603213e11d0f1b79dcab6b9d6428474b]

##### midori[commit=d2e74dcd603213e11d0f1b79dcab6b9d6428474b]

*Objectifs* : Tester l'efficacité de différents paramètres de restarts.

*Notes* : Les paramètres qui donnent les meilleurs résultats sont 4, 8 et 32 selon les instances.

L'heuristique utilisé est :

- DomOverDWeg*(nbActives),
- WDeg($\Delta$SBoxes) avec les contraintes fantômes,
- WDeg(abstractVars) avec les contraintes fantômes,
- DomOverDWeg*(all)

*DomOverDWeg est une version légèrement modifié qui ne prend pas les heuristiques maximales mais les trois meilleurs scores. Cela permet d'ajouter d'explorer des arbres différents lors des restarts.