from src.dataset_creation.feature_to_city import feature_to_city

from src.dataset_creation.make_grid import make_grid

def main(place_name: str, 
        project_name: str, 
        year: int, 
        scale: int,
        city_epsg: int):

    make_grid(place_name, scale)

    gdf = feature_to_city(place_name, project_name, year, scale, city_epsg)

    return gdf


# Call main to run all
if __name__ == "__main__":
    main()