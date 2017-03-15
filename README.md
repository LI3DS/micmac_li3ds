# micmac_li3ds

This project is a toolchain to fill li3ds datastore.

## Context

The goal of this project is to provide a set of tool for fill li3ds datastore from micmac output files. [Micmac] (https://github.com/micmacIGN/micmac "Micmac's Homepage") is a free open source photogrammetry software tools.

## Prerequisite

In the directory of this repository there are some example files from micmac : 
- AutoCal_Foc-12000_Cam-Caml024_20161205a.xml
- blinis_20161205.xml
- blocA_ori-export_023.txt (this file + timestamp from image will serve for generating a sbet file)


In addition of these files, a json file could be produced for the metadata of the mission. This json file will contain the references to other micmac files and provide the missing parameters in its json structure.

```
TODO: example
```

### Creation of the Earth sensor

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{rankdir=LR;compound=true;subgraph%20cluster_earth{label="Earth";ECEF[shape=box];Lambert93[shape=box];...[shape=box];}})

If not done already, it's necessary to create a sensor group that will regroup all the earth-fixed referentials (together with there postgis srid code).

```
[
    {
        "brand": "",
        "description": "Fixed Earth group of referentials, such as EPSG SRIDs",
        -- "id": 26,
        "model": "",
        "serial_number": "",
        "short_name": "Earth",
        "specifications": {},
        "type": "group"
    }
]
```

### Camera Calibration
Example Calib XML file : data/AutoCal_Foc-12000_Cam-Caml024_20161205a.xml

#### Creating a Camera Sensor

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{rankdir=LR;compound=true;subgraph%20cluster_sensor{label="Camera";euclidean[shape=box];idealImage[shape=box];distortedImage[shape=box,color=red];}})


3 referentials need to be created :
- 1. the Euclidean external referential (root=false): the camera node is at the origin, and it is oriented with +Z in front of the camera (the optical axis), +X to the right of the camera and +Y to the bottom of the camera.
- 2. ideal image frame  (root=false): X and Y are the raster coordinates in pixels that would used to lookup the pixel values if the camera were an ideal pinhole camera, Z is the inverse depth (measured along the optical axis).
- 3. distorted image frame  (root=true) : X and Y are the raster coordinates in pixels used to lookup the pixel values, Z is the inverse depth (measured along the optical axis).

#### Creating the Transfo-Tree of a Camera Calibration 
(given an pre-existing camera sensor created by a similar calib file)

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{rankdir=LR;compound=true;subgraph%20cluster_sensor%20{label="Camera";euclidean[shape=box];idealImage[shape=box];distortedImage[shape=box;color=red];{rank=same;euclidean%20idealImage%20distortedImage}subgraph%20cluster_transfotree%20{label="TransfoTree%20:%20AutoCal_Foc-12000_Cam-Caml024_20161205a.xml";projection;distortion;}euclidean->projection->idealImage;idealImage->distortion->distortedImage;}})

2 transforms need to be created :
- 1->2. Projective Pinhole Transform : ppa is given by`PP`, focal by `F`
- 2->3. Distorsion Transform : distorsion type and parameters are in `CalibDistortion` (see [micmac documentation](https://github.com/micmacIGN/Documentation/blob/master/DocMicMac.pdf))


### Sensor Group Calibration
Example Blini XML file : data/blinis_20161205.xml

#### Creating a Sensor Group

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{rankdir=LR;compound=true;subgraph%20cluster_sensor%20{label="Group";base[shape=box,color=red];023[shape=box];024[shape=box];025[shape=box];026[shape=box];}})

N+1 referentials need to be created :
- 1 is the base referential (root=true)
- 1 for each of the N XML nodes `ParamOrientSHC` should create a referential (root=false), named using `ParamOrientSHC/IdGrp`

#### Creating the Transfo-Tree of a Sensor Group Calibration
(given an pre-existing sensor group created by a similar blini file)

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{rankdir=LR;compound=true;subgraph%20cluster_sensor%20{label="Group";base[shape=box;color=red];023[shape=box];024[shape=box];025[shape=box];026[shape=box];subgraph%20cluster_transfotree%20{label="TransfoTree%20:%20blinis_20161205.xml";affine023;affine024;affine025;affine026;}}base->affine023->023;base->affine024->024;base->affine025->025;base->affine026->026;})

N affine transforms need to be created, linking the base referencial to each of the camera position referentials :
- The translation part is given by `ParamOrientSHC/Vecteur`
- The linear part, which happen to be a rotation, is given by `ParamOrientSHC/Rot`
