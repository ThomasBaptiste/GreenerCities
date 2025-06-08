import ee
import pathlib
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

# To load this file's output
def load_city_feature(city_name: str,
                    year: int)-> gpd.GeoDataFrame:
    # load grid for a given city
    # get path to grid file for a given city
    parent_path = pathlib.Path().parent.resolve()
    path = parent_path / f'data/processed/{city_name}_{year}.geojson'
    # load grid
    with open(path, 'r') as file:
        gdf = gpd.read_file(file)

    return gdf



def initialize_Earth_engine(project_name: str):
    # Initialize Earth Engine
    ee.Initialize(project=project_name)  

def load_city_grid(city_name: str)-> gpd.GeoDataFrame:
    # load grid for a given city
    # get path to grid file for a given city
    parent_path = pathlib.Path().parent.resolve()
    path = parent_path / f'data/grids/grid_{city_name}.geojson'
    # load grid
    with open(path, 'r') as file:
        grid = gpd.read_file(file)

    return grid

# Convert geometries to EE features
def gdf_to_ee_features(gdf: gpd.GeoDataFrame)-> ee.FeatureCollection:
    features = []
    for idx, row in gdf.iterrows():
        geom = row.geometry.__geo_interface__
        ee_geom = ee.Geometry(geom)
        features.append(ee.Feature(ee_geom, {'id': str(idx)}))
    return ee.FeatureCollection(features)