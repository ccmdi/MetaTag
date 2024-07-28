# EXPERIMENTAL: Potential feature in metatag.py

import json
import rasterio
import numpy as np
from rasterio.windows import Window
import argparse
import glob

def read_tif(src, coordinates, chunk_size=1000):
    results = []
    for i in range(0, len(coordinates), chunk_size):
        chunk = coordinates[i:i+chunk_size]
        row_offs, col_offs = zip(*[src.index(x, y) for x, y in chunk])
        
        row_min, col_min = min(row_offs), min(col_offs)
        row_max, col_max = max(row_offs), max(col_offs)
        
        window = Window(col_min, row_min, col_max - col_min + 1, row_max - row_min + 1)
        data = src.read(1, window=window)
        
        for (x, y), row, col in zip(chunk, row_offs, col_offs):
            value = data[row - row_min, col - col_min]
            if np.isclose(value, -3.4028234663852886e+38):
                value = "No Data"
            results.append({'longitude': x, 'latitude': y, 'value': float(value) if value != "No Data" else value})
        
    return results

def process_coordinates(tif_path, json_path, chunk_size=1000):
    with open(json_path, 'r') as json_file:
        coordinates = json.load(json_file)['customCoordinates']
    
    coord_pairs = [(coord['lng'], coord['lat']) for coord in coordinates]
    
    with rasterio.open(tif_path) as src:
        results = read_tif(src, coord_pairs, chunk_size)
    
    return results


if __name__ == "__main__":
    tif_files = glob.glob("*.tif")
    default_tif_path = tif_files[0] if tif_files else None

    args_parser = argparse.ArgumentParser(description="Read population from a TIF and tag JSON")
    args_parser.add_argument("tif_path", default=default_tif_path, help="Path to the GeoTIFF file")
    args_parser.add_argument("json_path", help="Path to the JSON file containing the coordinates")

    args = args_parser.parse_args()

    results = process_coordinates(args.tif_path, args.json_path)

    with open(args.json_path, 'r') as f:
        data = json.load(f)['customCoordinates']

    results_dict = {(result['latitude'], result['longitude']): result['value'] for result in results}

    for item in data:
        key = (item['lat'], item['lng'])
        if key in results_dict:
            item['pop'] = results_dict[key]
            item['extra']['tags'] = []
            if 'extra' in item and 'tags' in item['extra'] and results_dict[key] != "No Data":
                item['extra']['tags'].append("@POP: " + str(round(item['pop'], 1)))

    with open('output.json', 'w') as f:
        json.dump(data, f, indent=4)