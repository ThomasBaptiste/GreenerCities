from src.dataset_creation.util import (
    initialize_Earth_engine,
    load_city_grid,
    gdf_to_ee_features
)

from src.dataset_creation.variable_features import (
    get_landsat_collection,
    get_rural_reference_lst
)

from src.dataset_creation.interpolation import (
    split_city_grid,
    interpolate_to_grid,
    interpolate_single_image
)

from src.dataset_creation.static_features import (
    get_ghsl_features,
    get_water_features,
    get_elevation_features
)

from src.dataset_creation.feature_engineering import create_features

import geopandas as gpd


def feature_to_city(place_name: str, 
        project_name: str, 
        year: int, 
        scale: int,
        city_epsg: int):

    # Initialize gee project
    initialize_Earth_engine(project_name)
    
    # get city name 
    city_name = place_name.split(',')[0].strip().lower()
    # Load grid file (EPSG:2154 or similar)
    grid_gdf = load_city_grid(city_name)
    grid_gdf = grid_gdf.to_crs(epsg=4326)  # EE needs lat/lon (EPSG:4326)
    # Define EE grid
    ee_grid = gdf_to_ee_features(grid_gdf)

    # Initialize variable features (landsat collection)
    landsat = get_landsat_collection(ee_grid, year) 
    # Get number of images
    landsat_list = landsat.toList(landsat.size())
    num_landsat = landsat.size().getInfo()
    # Split the grid into smaller chunks due to ee limitations
    ee_grid_chunks = split_city_grid(ee_grid, max_size=5000)
    # Interpolate to city grid
    gdf_list = interpolate_to_grid(num_landsat, landsat_list, ee_grid_chunks, landsat, scale)
    # Now build GeoDataFrame
    gdf = gpd.GeoDataFrame(gdf_list, geometry='geometry', crs='EPSG:4326')


    # add static data to the dataframe
    # Initialize GHSL features
    ghsl = get_ghsl_features(ee_grid, year)
    # Interpolate to city grid
    ghsl_list = interpolate_single_image(ghsl, ee_grid_chunks, scale)
    # Build GeoDataframe
    ghsl_gdf = gpd.GeoDataFrame(ghsl_list, geometry='geometry', crs='EPSG:4326')
    # Combine to existing dataframe
    gdf = gdf.merge(ghsl_gdf.drop(columns=['geometry','date']), on='id', how='left')

    #Initialize water features (ESA WORLD COVER)
    water_img = get_water_features(ee_grid, year)
    # Interpolate to city grid
    water_list = interpolate_single_image(water_img, ee_grid_chunks, scale)
    # Build GeoDataframe
    water_gdf = gpd.GeoDataFrame(water_list, geometry='geometry', crs='EPSG:4326')
    # Combine to existing dataframe
    gdf = gdf.merge(water_gdf.drop(columns=['geometry', 'date']), on='id', how='left')

    # Initialize elevation static feature
    elevation_img = get_elevation_features(ee_grid)
    # Interpolate to city grid
    elevation_list = interpolate_single_image(elevation_img, ee_grid_chunks, scale)
    # Build GeoDataframe
    elevation_gdf = gpd.GeoDataFrame(elevation_list, geometry='geometry', crs='EPSG:4326')
    elevation_gdf.rename(columns={'mean': 'Elevation'}, inplace=True)
    # Combine to existing dataframe
    gdf = gdf.merge(elevation_gdf.drop(columns=['geometry', 'date']), on='id', how='left')


    # Get mean rural lst
    rural_lst = get_rural_reference_lst(ee_grid.geometry(), 10, year)
     
    
    # Create features we need for modeling
    gdf = create_features(gdf,rural_lst)


    # Project back to city espg
    gdf = gdf.to_crs(f'EPSG:{city_epsg}')
    # Save to GeoJSON file
    gdf.to_file(f'data/processed/{city_name}_{year}.geojson', driver='GeoJSON')


    return gdf
