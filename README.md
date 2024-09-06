# vlab_geotarget

## Installation

Make sure you have `pipx` installed, as well as Python 3.11 or higher, and the following should work:

``` shell
pipx install git+https://github.com/vlab-research/geotargeting.git
```

This should give you an executable called `vlab_geotarget`.

## Usage


To use `vlab_geotarget` do something like the following:

``` shell

vlab_geotarget \
    -places="your-project-folder/hotosm_ken_populated_places_points_shp.shp" \
    -pop="your-project-folder/ken_ppp_2020_1km_Aggregated_UNadj.tif" \
    -admin="your-project-folder/KEN_admin2_2002_DEPHA.shp" \
    -key="PROVINCE" \
    -mean=750 \
    -max=5000 \
    -out="your-project-folder/outs"
```

You will then get a set of files in the location designated by the `-out` parameter, which gives you the output of the procedure.

`places` - Shapefile of open street maps populated places for the country of interest
`pop` - Geotif raster file of population per 1km square
`admin` - Shapefile with admin level data (states/provinces/etc) for your country.
`key` - The column for the "name" of the administrative region
`mean` - The mean density for each concentric ring to be considered "urban." Once the next ring falls below this threshold, the circles will stop growing.
`max` - The max minimum for each concentric ring to be considered "urban." Once the next ring falls below this threshold, the circles will stop growing.
