import osmnx as ox
import numpy as np
from shapely.geometry import box
import geopandas as gpd
import os  

def get_epsg(place_name: str) -> str:
    # Extract the country from the place name (after the comma)
    country = place_name.split(',')[-1].strip().lower()

    if country == "france":
        return 2154  # Lambert-93 for France
    elif country == "spain":
        return 25830  # ETRS89 / UTM zone 30N for Spain
    elif country == "germany":
        return 25832  # ETRS89 / UTM zone 32N for Germany
    elif country == "italy":
        return 3003  # Italy, EPSG:3003 (Monte Mario) for Rome
    else:
        raise ValueError(f"EPSG code for country {country} not found.")

def make_grid_in_city(gdf: gpd.GeoDataFrame, cell_size: float, place_epsg: str) -> gpd.GeoDataFrame:
    # Define bounding box
    min_x, min_y, max_x, max_y = gdf.total_bounds

    # Initial square grid inside bounding box
    y_coords = np.arange(min_y, max_y, cell_size)
    x_coords = np.arange(min_x, max_x, cell_size)

    grid = []
    # Loop on coordinates
    for x in x_coords:
        for y in y_coords:
            cell = box(x, y, x + cell_size, y + cell_size)
            # Use union_all for merging geometries
            if cell.intersects(gdf.union_all()): 
                grid.append(cell)

    # Convert to GeoDataFrame format
    grid = gpd.GeoDataFrame(geometry=grid, crs=f"EPSG:{place_epsg}")

    return grid

def store_grid_to_file(grid: gpd.GeoDataFrame, place_name: str, place_epsg: str):
    # Extract the city name from the place_name (before the comma)
    city_name = place_name.split(",")[0].strip().lower()

    # Ensure the directory exists
    os.makedirs("data/grids", exist_ok=True)

    # Generate the file name with the city name in lowercase
    file_name = f"data/grids/grid_{city_name}.geojson"

    # Store the grid with the updated file name
    grid.to_file(file_name, driver="GeoJSON")

def main(place_name: str, cell_size: float):
    # Get the geodataframe from the chosen city using OSMnx
    gdf = ox.geocode_to_gdf(place_name)
    # Get EPSG code for the city
    place_epsg = get_epsg(place_name)
    # Project to meters for the given EPSG code
    gdf_proj = gdf.to_crs(epsg=place_epsg)
    # Make grid inside
    grid = make_grid_in_city(gdf_proj, cell_size, place_epsg)
    # Store the grid to file
    store_grid_to_file(grid, place_name, place_epsg)


# Call main to run both functions
if __name__ == "__main__":
    main()