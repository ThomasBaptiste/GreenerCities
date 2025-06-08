import geopandas as gpd
import pandas as pd

def create_features(gdf: gpd.GeoDataFrame,
                    rural_lst: pd.DataFrame)-> gpd.GeoDataFrame:
    # add other features over time
    gdf = create_building_height(gdf)
    gdf = create_built_surface(gdf)
    gdf = create_water_fraction(gdf)
    gdf = create_lst_anomaly(rural_lst,gdf)
    return gdf

def create_building_height(gdf: gpd.GeoDataFrame)-> gpd.GeoDataFrame:
    gdf["BuildingHeight"] = gdf["BuildingVolume"]/gdf["BuiltSurface"]
    gdf.drop(columns='BuildingVolume', inplace=True)
    return gdf

def create_built_surface(gdf: gpd.GeoDataFrame)-> gpd.GeoDataFrame:
    gdf["BuiltSurface"] = gdf["BuiltSurface"]/(100*100)
    return gdf

def create_lst_anomaly(rural_lst: pd.DataFrame,
                    gdf: gpd.GeoDataFrame)-> pd.Series:
    # Get the unique rural LST for the specific date
    for dates in rural_lst["date"]:
        rural_lst_value = rural_lst.loc[rural_lst["date"] == dates, "LST"].values[0]

        # Filter urban data for the same date
        urban_lsts = gdf.loc[gdf["date"] == dates, "LST"].values

        # Subtract the rural LST from each urban LST for that date
        lst_difference = urban_lsts - rural_lst_value

        gdf.loc[gdf["date"] == dates, "LST_anomaly"] = lst_difference
    return gdf

def create_water_fraction(gdf: gpd.GeoDataFrame)-> gpd.GeoDataFrame:
    gdf["WaterFraction"] = gdf["WaterFraction"]/(100.0)
    return gdf