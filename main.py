from src.ingest import feature_to_city
from src.ingest import make_grid
import time


start = time.time()

gdf = feature_to_city.main('lyon,france', 'ee-thomasbaptiste45', 2021, 100)

end = time.time()

print(end - start)