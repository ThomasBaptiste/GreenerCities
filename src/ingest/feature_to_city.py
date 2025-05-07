import ee
import pathlib
import geopandas as gpd
import pandas as pd
import json
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

#----------------------------------------------------#
# VARIABLE FEATURES
#----------------------------------------------------#

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



# Extract Land Surface Temperature (LST) in Celsius
def get_lst(img: ee.Image) -> ee.Image:
    lst = img.select("ST_B10") \
              .multiply(0.00341802) \
              .add(149.0) \
              .subtract(273.15) \
              .rename("LST")
    return lst

# Extract NDVI (Normalized Difference Vegetation Index)
def get_ndvi(img: ee.Image) -> ee.Image:
    ndvi = img.normalizedDifference(["SR_B5", "SR_B4"]) \
              .rename("NDVI")
    return ndvi

def process_image(img: ee.image) -> ee.Image: 
    # Convert ST_B10 to LST in Kelvin
    lst = get_lst(img)
    #extract NDVI (vegetation)
    ndvi = get_ndvi(img)
    date = img.date().format("YYYY-MM-dd")
    return lst.addBands(ndvi).set('date',date)


# Get collection containing LST, NDVI
def get_landsat_collection(ee_grid: ee.FeatureCollection,
                             year: int) -> ee.ImageCollection:
    start_date = f'{year}-01-01'
    end_date = f'{year}-12-31'

    collection = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(ee_grid.geometry())
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUD_COVER", 10))
        .map(process_image)
    )

    return collection

# Split the grid into smaller chunks (subsets)
def split_city_grid(collection: ee.ImageCollection, 
                    max_size=5000) -> list:
    num_chunks = (collection.size().getInfo() // max_size) + 1
    chunks = []
    for i in range(num_chunks):
        start = i * max_size
        end = (i + 1) * max_size
        chunk = collection.toList(collection.size()).slice(start, end)
        chunks.append(ee.FeatureCollection(chunk))
    return chunks


# Interpolate the image's data for the features to the city's grid
def interpolate_to_grid(num_images: int,
                        image_list: ee.List, 
                        ee_grid_chunks: list, 
                        collections: ee.ImageCollection, 
                        scale: int) -> list:

    # List to hold all results
    gdf_list = [] 

    for i in range(num_images):
        img = ee.Image(image_list.get(i))
        # Retrieve image date string
        date_str = img.get('date').getInfo() 

        # Process each chunk separately
        for chunk in ee_grid_chunks:
            zonal_stats = img.reduceRegions(
                collection=chunk,
                reducer=ee.Reducer.mean(),
                scale=scale,
            )
            
            # Get results as a list of dictionaries
            results = zonal_stats.getInfo()['features']

            # Extract into DataFrame
            for feature in results:
                # Convert GeoJSON to Shapely geometry
                geometry = shape(feature['geometry'])  
                properties = feature['properties']
                properties['date'] = date_str
                # Add image statistics to properties (LST, NDVI, etc.)
                properties['geometry'] = geometry
                    # Append to list
                gdf_list.append(properties)

    return gdf_list
#----------------------------------------------------#
# STATIC FEATURES
#----------------------------------------------------#

def get_ghsl_features(ee_grid: ee.FeatureCollection,
                    year: int) -> ee.Image:
    # Supported GHSL years
    if 2014 <= year <= 2016:
        ghsl_year = 2015
    elif 2019 <= year <= 2021:
        ghsl_year = 2020
    else:
        raise ValueError("GHSL data is only available for 2015 and 2020.")

    # Get GHSL layers and reproject to EPSG:4326 with appropriate scale
    built_surface = (
        get_built_surface(ghsl_year)
        .reproject(crs='EPSG:4326', scale=100)  # Adjust scale based on GHSL's native resolution
    )

    building_volume = (
        get_building_volume(ghsl_year)
        .reproject(crs='EPSG:4326', scale=100)
    )

    population = (
        get_population(ghsl_year)
        .reproject(crs='EPSG:4326', scale=100)
    )

    # Combine into one image
    ghsl_stack = built_surface.addBands([building_volume, population])

    # Clip to city geometry if provided
    if ee_grid:
        ghsl_stack = ghsl_stack.clip(ee_grid.geometry())

    return ghsl_stack

# get built_surface in m^2 from GHSL
def get_built_surface(year: int) -> ee.Image:
    return (
        ee.Image(f'JRC/GHSL/P2023A/GHS_BUILT_S/{year}')
        .select('built_surface')
        .rename('BuiltSurface')
    )

# get built_volume in m^3 from GHSL
def get_building_volume(year: int) -> ee.Image:
    return (
        ee.Image(f'JRC/GHSL/P2023A/GHS_BUILT_V/{year}')
        .select('built_volume_total')
        .rename('BuildingVolume')
    )

# get pop per epoch from GHSL
def get_population(year: int) -> ee.Image:
    return (
        ee.Image(f'JRC/GHSL/P2023A/GHS_POP/{year}')
        .select('population_count')
        .rename('Population')
    )


# Apply static feature image to the city grid 
def interpolate_single_image(img: ee.Image, 
                             ee_grid_chunks: list, 
                             scale: int = 100) -> list:
    # Get image date string
    date_str = img.get('date').getInfo()

    gdf_list = []

    # Process each grid chunk
    for chunk in ee_grid_chunks:
        zonal_stats = img.reduceRegions(
            collection=chunk,
            reducer=ee.Reducer.mean(),
            scale=scale,
        )

        # Extract results
        results = zonal_stats.getInfo()['features']

        for feature in results:
            geometry = shape(feature['geometry'])
            properties = feature['properties']
            properties['date'] = date_str
            properties['geometry'] = geometry
            gdf_list.append(properties)

    return gdf_list


#----------------------------------------------------#
# RURAL REFERENCE
#----------------------------------------------------#
# Obtain the mean rural reference LST for each date of the dataset.
# Buffer decides the size of the area studied around the city to find rural area.
def get_rural_reference_lst(ee_grid_geom:ee.Geometry.Polygon, 
                            buffer_km: float, 
                            year: int)-> pd.DataFrame:

    # get all dates of the year
    start_date = f'{year}-01-01'
    end_date = f'{year}-12-31'

    # Step 1: Load land cover image and create rural mask (exclude urban = 50)
    # Only two land covers datasets available, but they are quite new.
    if year <= 2020:
        landcover_year = 2020
        dataset_id = "ESA/WorldCover/v100/2020"
    else:
        landcover_year = 2021
        dataset_id = "ESA/WorldCover/v200/2021"
    landcover = ee.Image(dataset_id).select("Map")
    rural_classes = [10, 20, 30, 40, 60, 70, 80, 90, 100]
    # rural_mask = landcover.neq(50)  # non-urban = 1
    rural_mask = landcover.remap(rural_classes, [1]*len(rural_classes)).eq(1)

    # Step 2: Create buffer around city geometry
    buffer_m = buffer_km * 1000
    buffer_geom = ee_grid_geom.buffer(buffer_m)

    # Step 3: Remove the inner city to get only surrounding rural ring
    rural_area = buffer_geom.difference(ee_grid_geom)

    # Step 4: Get mean LST image and apply rural mask
    collection = (
        ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        .filterBounds(buffer_geom)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt('CLOUD_COVER', 10))
        .map(lambda img: get_lst(img).set('date', img.date().format('YYYY-MM-dd')))
    )

    images = collection.toList(collection.size())
    n_images = images.size().getInfo()

    rural_lst_by_date = []

    for i in range(n_images):
        image = ee.Image(images.get(i))
        date = image.get('date').getInfo()
        masked = image.updateMask(rural_mask)

        mean = masked.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=rural_area,
            scale=100,
            maxPixels=1e13
        )

        mean_lst = mean.getInfo().get('LST')
        if mean_lst is not None:
            rural_lst_by_date.append({'date': date, 'LST': mean_lst})

    return pd.DataFrame(rural_lst_by_date)

def get_lst_anomaly(rural_lst: pd.DataFrame,
                    gdf: gpd.GeoDataFrame)-> pd.Series:
    # Get the unique rural LST for the specific date
    for dates in rural_lst["date"]:
        rural_lst_value = rural_lst.loc[rural_lst["date"] == dates, "LST"].values[0]

        # Filter urban data for the same date
        urban_lsts = gdf.loc[gdf["date"] == dates, "LST"].values

        # Subtract the rural LST from each urban LST for that date
        lst_difference = urban_lsts - rural_lst_value

        gdf.loc[gdf["date"] == dates, "LST_anomaly"] = lst_difference

    return gdf["LST_anomaly"]

#----------------------------------------------------#
#----------------------------------------------------#
#----------------------------------------------------#

def main(place_name: str, 
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

    # Get mean rural lst
    rural_lst = get_rural_reference_lst(ee_grid.geometry(), 10, year)
    # Compute LST anomaly and add to dataframe
    gdf["LST_anomaly"] = get_lst_anomaly(rural_lst, gdf)


    # Project back to city espg
    gdf = gdf.to_crs(f'EPSG:{city_epsg}')
    # Save to GeoJSON file
    gdf.to_file(f'data/processed/{city_name}_{year}.geojson', driver='GeoJSON')


    return gdf


# Call main to run all
if __name__ == "__main__":
    main()