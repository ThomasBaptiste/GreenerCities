import pytest
from unittest import mock
import geopandas as gpd
from shapely.geometry import Point, Polygon
from ingest.make_grid import get_epsg, make_grid_in_city, store_grid_to_file, main

def test_get_espg():
    place_name = 'paris,france'  # city in france
    assert get_epsg(place_name) == 2154  # France code

def test_make_grid_in_city_simple():
    poly = Polygon([(0,0), (0,5), (5,5), (5,0)])
    gdf = gpd.GeoDataFrame(geometry=[poly], crs="EPSG:32633")

    grid = make_grid_in_city(gdf, 1, 32633)

    assert not grid.empty
    assert all(cell.area == 1 for cell in grid.geometry)  # each should be 1x1 m2

@mock.patch('geopandas.GeoDataFrame.to_file')
def test_store_grid_to_file(mock_to_file):
    grid = gpd.GeoDataFrame(geometry=[])
    
    store_grid_to_file(grid, "Paris,France", 2154 )
    
    mock_to_file.assert_called_once()
    args, kwargs = mock_to_file.call_args
    assert "data/grids/grid_paris.geojson" in args[0]

@mock.patch('ingest.make_grid.get_epsg', return_value=2154 )
@mock.patch('geopandas.GeoDataFrame.to_file')
@mock.patch('osmnx.geocode_to_gdf')
def test_main(mock_geocode, mock_to_file, mock_get_epsg):
    mock_gdf = gpd.GeoDataFrame(geometry=[Point(12.4924, 41.8902)], crs="EPSG:4326")
    mock_geocode.return_value = mock_gdf

    main("Paris, France", 500)

    mock_geocode.assert_called_once_with("Paris, France")
    mock_to_file.assert_called_once()
    mock_get_epsg.assert_called_once()