As of now:

Le code "test" du notebook dl la série d'image trié par date et extrait LST, NDVI. On calcule aussi la LST rurale alentour et on ajoute la lst_anomalie.
Ensuite enregistrer dans un fichier.

LES trucs numéro 1 à faire:
_mettre tout ça dans un fichier python en fonction modulables.
    > verifier les données GHSL
    >Maintenant il faut faire l'addition pour les autres données satelitaires avec toute leurs spécificités.
_verifier qu'il n'y a pas de redite
_faire des unit tests
_test les scores UHI pour une premiere visualisation de la ville
_checker si il y a un truc approximatif pour faire temp de l'air à partir de LST.
_un ptit fichier avec les fonctions de visus, ça sera utile à terme forcement.
_verifier la temp

Ensuite:
    > voir les autres sources comment les incorporer au jeu de données apres (pas sur qu'on est les meme dates, comment ça fonctionne)





⬇️ Output Format for ML Training:

You want a DataFrame like this:
cell_id	date	LST	NDVI	Urban_Class	...
1	2021-07-03	298.2	0.54	1	...
1	2021-08-10	296.5	0.62	1	...
2	2021-07-03	300.1	0.33	2	...
🔁 Looping over Time

Since EE limits memory and getInfo() can break for large requests, you could loop over months or years, and for each:

    Load the collection for that window,

    Map LST + other features,

    Run zonal stats per grid cell,

    Collect the results locally and append them.



Afterwards, we will need to check public datasets to find:
 > Which features we want
 > How we can access them
 > How to get them for the city only

Next step will be to clean/format the data