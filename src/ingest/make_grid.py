# make_grid.py
import osmnx as ox
import numpy as np
from shapely.geometry import box
import geopandas as gpd
import re

def get_city_boundaries_in_meters(place_name: str) -> gpd.GeoDataFrame:
    # get the geodataframe from the chosen city using OSMnx
    gdf = ox.geocode_to_gdf(place_name)
    # convert degrees to meters
    gdf_proj = gdf.to_crs(epsg=3857)

    return gdf_proj


def make_grid_in_city(gdf: gpd.GeoDataFrame , cell_size: float) -> gpd.GeoDataFrame:
    # define bounding box
    min_x, min_y, max_x, max_y = gdf.total_bounds

    # initial square grid inside bounding box
    y_coords = np.arange(min_y,max_y, cell_size)
    x_coords = np.arange(min_x,max_x, cell_size)

    grid = []
    # loop on coordinates
    for x in x_coords:
        for y in y_coords:
            cell = box(x,y,x+cell_size,y+cell_size)
            # union_all makes the geometry of the city into one big polygon
            # checks if square grid is inside city's boundaries
            if cell.intersects(gdf.union_all()): 
                grid.append(cell)

    # convert to geodataframe format
    grid = gpd.GeoDataFrame(geometry=grid, crs="EPSG:3857")

    return grid

def store_grid_to_file(grid: list, place_name: str):
    # Extract the city name from the place_name (before the comma)
    city_name = place_name.split(",")[0].strip().lower()
    
    # Generate the file name with the city name in lowercase
    file_name = f"data/raw/grid_{city_name}.geojson"
    
    # Store the grid with the updated file name
    grid.to_crs("EPSG:3857").to_file(file_name, driver="GeoJSON")

#----------------------------------------------------------------------------------


def main(place_name: str, cell_size: float) -> gpd.GeoDataFrame:
    # get boundaries
    gdf = get_city_boundaries_in_meters(place_name)
    # make grid inside
    grid = make_grid_in_city(gdf, cell_size)
    # store the boundaries for future uses
    store_grid_to_file(grid, place_name)

    return grid

# Call main to run both functions
if __name__ == "__main__":
    main()