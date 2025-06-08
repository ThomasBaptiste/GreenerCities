import ee


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

def get_water_features(ee_grid: ee.FeatureCollection,
                       year: int) -> ee.Image:
    water_occurence = get_water_occurence_image(year)
    dist_to_water = get_water_distance_image()

    # Combine both into one multi-band image
    water_stack = water_occurence.addBands(dist_to_water)

    if ee_grid:
        water_stack = water_stack.clip(ee_grid.geometry())

    return water_stack

# get water percentage
def get_water_occurence_image(year: int) -> ee.Image:
    # Returns occurrence percentage directly (0–100)
    water_occurrence = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence')
    return water_occurrence.rename("WaterFraction")

def get_water_mask_image(year: int) -> ee.Image:
    water_occurrence = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence')
    water_mask = water_occurrence.gte(50).rename("WaterMask")  # presence in ≥50% of the time
    return water_mask

# Get distance to nearest water in meters
def get_water_distance_image() -> ee.Image:
    water_mask = get_water_mask_image(2020).gte(50)  # fixed year as mostly stable
    # Distance to water (use inverted mask for non-water)
    dist = water_mask.Not().fastDistanceTransform().sqrt().multiply(30).rename("DistToWater")
    return dist


def get_elevation_features(ee_grid: ee.FeatureCollection) -> ee.Image:
    elevation = get_elevation_image().reproject(crs='EPSG:4326', scale=30)
    if ee_grid:
        elevation = elevation.clip(ee_grid.geometry())
    return elevation

def get_elevation_image() -> ee.Image:
    elevation = ee.Image("USGS/SRTMGL1_003").select('elevation').rename('Elevation')
    return elevation