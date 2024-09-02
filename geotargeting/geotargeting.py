import geopandas as gpd
import pandas as pd
import numpy as np
from rasterstats import zonal_stats
from clize import Parameter, run
import rasterio
import os
import argparse

def buffer_city(pop_path, cities, o, i):
    proposed = cities.to_crs(3857).buffer(o)
    previous = cities.to_crs(3857).buffer(i)
    cc = proposed.difference(previous)
    cc = cc.to_crs(4326)
    stats = zonal_stats(cc, pop_path)
    cities['max_density'] = np.array([d['max'] if d['max'] else 0 for d in stats])
    cities['mean_density'] = np.array([d['mean'] if d['mean'] else 0 for d in stats])
    cities['geometry'] = proposed
    cities['rad'] = o / 1000
    return cities


def step(pop_path, mean_lim, max_lim, cities, o, i):
    cities = cities.copy()
    proposed = buffer_city(pop_path, cities, o, i)
    mask = (proposed.mean_density > mean_lim) | (proposed.max_density > max_lim)
    return proposed[mask], proposed[~mask]


def algo(pop_path, mean_lim, max_lim, cities, min_rad):
    # first round
    outer = 1000
    inner = 0
    cities, kicked_out = step(pop_path, mean_lim, max_lim, cities, outer, inner)
    finished = kicked_out
    i = 0
    while cities.shape[0] > 0 and i < 10:
        print(f"Round: {i}")
        i += 1
        inner = outer
        outer += 1000
        survived, kicked_out = step(pop_path, mean_lim, max_lim, cities, outer, inner)
        finished = pd.concat([finished, kicked_out])
        cities = survived.reset_index(drop=True)

    finished = pd.concat([finished, cities])
    return finished[finished.rad >= min_rad].reset_index(drop=True)


def filter_overlap(finished):
    bads = []

    for i, g in finished.geometry.items():
        f = finished.drop(i).drop(bads).reset_index()
        mask = f.intersects(g)
        if mask.sum() >= 1:
            amt = f[mask].intersection(g).area
            overlapping = amt / g.area > 0.8
            if overlapping.sum() >= 1:
                bads.append(i)

    return finished.drop(bads).reset_index(drop=True)


def get_total_population(pop_path):
    dataset = rasterio.open(pop_path)
    return dataset.read(1, masked=True).sum()


def add_total_population(finished, pop_path):
    stats = zonal_stats(finished.to_crs(4326), pop_path, stats=['sum'])
    total_pop = [round(d['sum']) for d in stats]
    finished['overlap_population'] = total_pop

    tot = get_total_population(pop_path)
    tot_covered = finished.overlap_population.sum()

    print(f"""
Total Population: {tot}
Covered Population: {tot_covered}
Covered Ratio: {tot_covered / tot}
    """)
    return finished


def make_city_shapes(mean_lim, max_lim, populated_places, population_density, place_types = {'city'}, min_rad = 1.0):
    places = gpd.read_file(populated_places)
    if not places.crs:
        places = places.set_crs(4326)
    cities = places[places.place.isin(place_types)].reset_index(drop=True)
    finished = algo(population_density, mean_lim, max_lim, cities, min_rad)
    finished = filter_overlap(finished)
    finished = add_total_population(finished, population_density)
    return finished


def _get_overlap(base, shape, name_var):
    s = base[base.intersects(shape)]
    if len(s) > 0:
        return s[name_var]
    return None

def prepare_targeting(city_shapes, regions, name_var_region):
    city_shapes = city_shapes.copy()

    city_shapes['lng'] = city_shapes.to_crs(4326).geometry.map(lambda g: g.centroid.coords[0][0])
    city_shapes['lat'] = city_shapes.to_crs(4326).geometry.map(lambda g: g.centroid.coords[0][1])
    states = gpd.read_file(regions).to_crs(3857)


    def get_states(c):
        s = states[states.intersects(c)]
        if len(s) > 0:
            return [x.strip() for x in s[name_var_region]]
        return []

    overlaps = [{'region': s, 'name': c['name'], 'total_population': c.overlap_population} for _, c in city_shapes.iterrows() for s in get_states(c.geometry)]
    cities = [{'region': s, 'name': c['name'], 'total_population': c.overlap_population} for _, c in city_shapes.iterrows() for s in get_states(c.geometry.centroid)]

    def prep(x):
        return (pd.DataFrame(x)
                .merge(city_shapes)[['region', 'name', 'total_population', 'rad', 'lat', 'lng']]
                .sort_values('name').reset_index(drop=True))

    return prep(cities), prep(overlaps)


def main(populated_places_path, population_raster_path, mean_minimum, max_minimum, out_dir, admin_shapes = None, admin_shape_key = None):

    print(f"""
Generating buffers based on:

Mean Minimum: {mean_minimum}
Max Minimum: {max_minimum}
    """)

    finished = make_city_shapes(mean_minimum,
                            max_minimum,
                            populated_places_path,
                            population_raster_path,
                            {'city', 'town'},
                            2.0)

    finished.to_file(os.path.join(out_dir, "urban-areas.shp"))

    if admin_shapes and admin_shape_key:
        cities, overlaps = prepare_targeting(finished, admin_shapes, admin_shape_key)

        cities.to_csv(os.path.join(out_dir,"centers-per-state.csv"), index=False)
        overlaps.to_csv(os.path.join(out_dir,"overlap-per-state.csv"), index=False)


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('-places', '--populated-places-path',  type=str, required=True)
    parser.add_argument('-pop', '--population-raster-path',  type=str, required=True)
    parser.add_argument('-mean', '--mean-minimum',  type=int, required=True)
    parser.add_argument('-max', '--max-minimum',  type=int, required=True)
    parser.add_argument('-admin', '--admin-shapes',  type=str, required=True)
    parser.add_argument('-key', '--admin-shape-key',  type=str, required=True)
    parser.add_argument('-out', '--out-dir',  type=str, required=True)

    args = parser.parse_args()

    main(args.populated_places_path,
         args.population_raster_path,
         args.mean_minimum,
         args.max_minimum,
         args.out_dir,
         args.admin_shapes,
         args.admin_shape_key)

run()
