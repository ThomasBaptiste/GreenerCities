import ee
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import numpy as np

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

def get_albedo(img):
    # Scale reflectance bands properly
    sr_b2 = img.select('SR_B2').multiply(0.0000275).add(-0.2)
    sr_b3 = img.select('SR_B3').multiply(0.0000275).add(-0.2)
    sr_b4 = img.select('SR_B4').multiply(0.0000275).add(-0.2)
    sr_b5 = img.select('SR_B5').multiply(0.0000275).add(-0.2)
    sr_b6 = img.select('SR_B6').multiply(0.0000275).add(-0.2)
    sr_b7 = img.select('SR_B7').multiply(0.0000275).add(-0.2)

    albedo = (
        sr_b2.multiply(0.356)
        .add(sr_b3.multiply(0.130))
        .add(sr_b4.multiply(0.373))
        .add(sr_b5.multiply(0.085))
        .add(sr_b6.multiply(0.072))
        .add(sr_b7.multiply(0.036))
        .subtract(0.0018)
        .rename('Albedo')
    )
    return img.addBands(albedo)

def process_image(img: ee.image) -> ee.Image: 
    # Convert ST_B10 to LST in Kelvin
    lst = get_lst(img)
    #extract NDVI (vegetation)
    ndvi = get_ndvi(img)
    albedo = get_albedo(img).select('Albedo')
    date = img.date().format("YYYY-MM-dd")
    return lst.addBands([ndvi, albedo]).set('date', date)


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

#----------------------------------------------------#
# METEO FEATURES
#----------------------------------------------------#


def get_daily_wind_speed_single_pixel(row):
    date = row['date'] # Use the normalized date for filtering GEE data
    point = row['centroid_geometry'] # This is a shapely Point object in Lat/Lon

    ee_point = ee.Geometry.Point(point.x, point.y)

    era5_daily = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR') \
               .filterDate(date.strftime('%Y-%m-%d'), (date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')) \
               .select(['u_component_of_wind_10m', 'v_component_of_wind_10m'])

    def calculate_wind_speed(image):
        u = image.select('u_component_of_wind_10m')
        v = image.select('v_component_of_wind_10m')
        wind_speed = u.pow(2).add(v.pow(2)).sqrt().rename('wind_speed')
        return wind_speed.copyProperties(image, ['system:time_start', 'system:time_end'])

    wind_speed_collection = era5_daily.map(calculate_wind_speed)

    era5_nominal_resolution_m = 27800

    try:
        if wind_speed_collection.size().getInfo() > 0:
            wind_image = wind_speed_collection.first()
            wind_value = wind_image.sample(
                region=ee_point,
                scale=era5_nominal_resolution_m,
                projection=wind_image.select('wind_speed').projection()
            ).first().get('wind_speed').getInfo()
            return wind_value
        else:
            return np.nan
    except ee.EEException as e:
        print(f"Error processing {date} at {point}: {e}")
        return np.nan


# GEE Function for Solar Radiation
def get_daily_solar_radiation_single_pixel(row):
    """
    Fetches the daily ERA5-Land surface_solar_radiation_downwards for a single point (centroid) and date.
    Assumes row['date'] is a pandas datetime object and row['centroid_geometry'] is a shapely Point in EPSG:4326.
    """
    date_obj = row['date'] # Using 'date' as per requested structure
    point = row['centroid_geometry'] # Using 'centroid_geometry' as per requested structure

    ee_point = ee.Geometry.Point(point.x, point.y)

    start_date_str = date_obj.strftime('%Y-%m-%d')
    end_date_str = (date_obj + pd.Timedelta(days=1)).strftime('%Y-%m-%d')

    # Using ERA5-Land Daily Aggregated for Surface Solar Radiation Downwards
    era5_land_solar = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR') \
                      .filterDate(start_date_str, end_date_str) \
                      .select(['surface_solar_radiation_downwards_sum']) # Select the SSRD band

    era5_land_nominal_resolution_m = 9000 # Corrected for ERA5-Land

    try:
        collection_size = era5_land_solar.size().getInfo()
        if collection_size > 0:
            solar_image = era5_land_solar.first()
            solar_value = solar_image.sample(
                region=ee_point,
                scale=era5_land_nominal_resolution_m,
                projection=solar_image.select('surface_solar_radiation_downwards_sum').projection()
            ).first().get('surface_solar_radiation_downwards_sum').getInfo()
            return solar_value
        else:
            return np.nan
    except ee.EEException as e:
        print(f"Error processing {start_date_str} at {point}: {e}. Returning NaN.")
        return np.nan
    except Exception as e:
        print(f"General Error for {start_date_str} at {point}: {e}. Returning NaN.")
        return np.nan



# Wrapper function for wind speed and solar radiation
def add_daily_climate_data(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Adds daily wind speed and solar radiation to the GeoDataFrame.
    It computes these values for the first row of each unique date and applies them
    to all other rows with the same date.
    """
    # Prepare centroids for the current gdf
    gdf['centroid_geometry'] = gdf.geometry.centroid
    gdf['centroid_geometry'] = gdf['centroid_geometry'].to_crs("EPSG:4326")

    # Normalize date for consistent daily keys and GEE filtering
    gdf['normalized_date_for_merge'] = gdf['date'].dt.normalize()

    unique_dates_for_processing = gdf['normalized_date_for_merge'].unique()

    representative_climate_data = []

    # Removed tqdm loop
    for u_norm_date in unique_dates_for_processing:
        representative_row_candidates = gdf[gdf['normalized_date_for_merge'] == u_norm_date]
        if 'original_id' in representative_row_candidates.columns:
            representative_row = representative_row_candidates.sort_values(by='original_id').iloc[0]
        else:
            representative_row = representative_row_candidates.iloc[0]

        temp_row_for_gee_call = representative_row.copy()
        temp_row_for_gee_call['date'] = temp_row_for_gee_call['normalized_date_for_merge']

        wind_speed = get_daily_wind_speed_single_pixel(temp_row_for_gee_call)
        solar_radiation = get_daily_solar_radiation_single_pixel(temp_row_for_gee_call)

        representative_climate_data.append({
            'normalized_date_for_merge': u_norm_date,
            'daily_wind_speed_ms': wind_speed,
            'daily_solar_radiation': solar_radiation
        })

    representative_df_climate = pd.DataFrame(representative_climate_data)

    gdf = gdf.merge(representative_df_climate, on='normalized_date_for_merge', how='left')

    # Drop the temporary columns created within this function
    gdf = gdf.drop(columns=['centroid_geometry', 'normalized_date_for_merge'], errors='ignore')

    return gdf

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