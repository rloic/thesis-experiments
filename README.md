# Thesis experiments

## Archives

### Fichiers
- midori[commit=d2e74dcd603213e11d0f1b79dcab6b9d6428474b]
- aes[commit=a32f5dbbe36ceaa5a732be2247df378c59551916]

#### Midori
##### midori[commit=d2e74dcd603213e11d0f1b79dcab6b9d6428474b]

*Objectifs* : Tester l'efficacité de différents paramètres de restarts.

*Notes* : Les paramètres qui donnent les meilleurs résultats sont 4, 8 et 32 selon les instances.

L'heuristique utilisé est :

- DomOverDWeg*(nbActives),
- WDeg($\Delta$SBoxes) avec les contraintes fantômes,
- WDeg(abstractVars) avec les contraintes fantômes,
- DomOverDWeg*(all)

*DomOverDWeg est une version légèrement modifié qui ne prend pas les heuristiques maximales mais les trois meilleurs scores. Cela permet d'ajouter d'explorer des arbres différents lors des restarts.

#### AES
##### aes[commit=a32f5dbbe36ceaa5a732be2247df378c59551916]

*Objectifs* : Test sur AES de l'ajout des sommes cumulées pour nbActives

L'heuristique utilisée est :
- Search.minDomLB(nbActives),
- DomOverDWeg*($\Delta$SBoxes),
- DomOverDWeg*(abstractVars),
- DomOverDWeg*(other)

*DomOverDWeg est une version modifié. Lorsque la contrainte qui engendre le conflit est *abstractXOR*, on renforce l'ensemble des autres contraintes qui sont associées à la variable responsable de la contradiction.