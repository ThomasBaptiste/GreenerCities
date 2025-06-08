import ee
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

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
