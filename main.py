from src.dataset_creation import main
import time


start = time.time()

gdf = main.main('lyon,france', 'ee-thomasbaptiste45', 2021, 100)

end = time.time()

print(end - start)