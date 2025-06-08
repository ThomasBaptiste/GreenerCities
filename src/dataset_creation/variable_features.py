import ee
import geopandas as gpd
import pandas as pd

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