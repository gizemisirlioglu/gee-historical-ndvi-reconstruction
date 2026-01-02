"""
02_harmonize_ndvi_time_series.py

Description:
    Harmonizes historical NDVI data (e.g., Landsat MSS) to a reference distribution 
    (e.g., Landsat TM) using a Percentile Mapping approach (P2-P98).

Usage:
    python 02_harmonize_ndvi_time_series.py --config config_harmonize.json

Author: [Adın Soyadın]
License: MIT
"""

import ee
import json
import argparse
import sys
import os

# ==============================================================================
# 1. SETUP & CONFIG LOADER
# ==============================================================================

def load_config(config_path):
    """Loads configuration from a JSON file."""
    if not os.path.exists(config_path):
        print(f"ERROR: Config file '{config_path}' not found.")
        sys.exit(1)
        
    with open(config_path, 'r') as f:
        return json.load(f)

def init_gee(project_id):
    """Initializes Google Earth Engine."""
    try:
        ee.Initialize(project=project_id)
        print(f">> GEE Initialized (Project: {project_id})")
    except Exception:
        print(">> Authenticating GEE...")
        ee.Authenticate()
        ee.Initialize(project=project_id)

# ==============================================================================
# 2. CORE FUNCTIONS
# ==============================================================================

def load_ndvi(asset_id, aoi):
    """Loads a single-band NDVI image, ensures float type, and clips to AOI."""
    img = ee.Image(asset_id).toFloat()
    img = ee.Image(ee.Algorithms.If(img.bandNames().length().gt(1), img.select([0]), img))
    return img.rename("NDVI").clip(aoi)

def get_percentiles(img, scale, aoi):
    """Computes the 2nd and 98th percentiles over the AOI."""
    stats = img.reduceRegion(
        reducer=ee.Reducer.percentile([2, 98]),
        geometry=aoi,
        scale=scale,
        bestEffort=True,
        maxPixels=1e13
    )
    p2  = ee.Number(stats.get("NDVI_p2"))
    # Ensure p98 > p2 to avoid div by zero
    p98 = ee.Number(stats.get("NDVI_p98")).max(p2.add(1e-6))
    return p2, p98

def harmonize_image(target_img, target_scale, ref_p2, ref_p98, aoi):
    """
    Applies percentile mapping to harmonize the target image.
    Formula: New = [(Old - Old_P2) / (Old_P98 - Old_P2)] * (Ref_P98 - Ref_P2) + Ref_P2
    """
    # 1. Get statistics of the target image
    t_p2, t_p98 = get_percentiles(target_img, target_scale, aoi)
    
    # 2. Normalize target to 0-1 range
    normalized = target_img.subtract(t_p2).divide(t_p98.subtract(t_p2))
    
    # 3. Scale to Reference range
    remapped = normalized.multiply(ref_p98.subtract(ref_p2)).add(ref_p2)
    
    # 4. Clamp
    return remapped.clamp(ref_p2, ref_p98).clamp(-1, 1).rename("NDVI")

def export_to_drive(img, year, scale, folder, aoi):
    """Exports the processed image to Google Drive."""
    filename = f"NDVI_{year}_Harmonized_to_1985"
    
    task = ee.batch.Export.image.toDrive(
        image=img,
        description=filename,
        folder=folder,
        fileNamePrefix=filename,
        region=aoi,
        scale=scale,
        maxPixels=1e13
    )
    task.start()
    print(f"   [Task Started] {filename} -> Drive/{folder} (scale={scale}m)")

# ==============================================================================
# 3. MAIN EXECUTION
# ==============================================================================

def main():
    # Parse Arguments
    parser = argparse.ArgumentParser(description="NDVI Harmonization Script")
    parser.add_argument('--config', type=str, default='config_harmonize.json', help="Path to config file")
    args = parser.parse_args()
    
    # Load Config
    print(f">> Loading configuration from {args.config}...")
    CFG = load_config(args.config)
    
    # Init GEE
    init_gee(CFG['project_id'])
    
    # Load AOI
    AOI = ee.FeatureCollection(CFG['aoi_asset']).geometry()
    
    print(">> Starting Harmonization Process...")
    
    # 1. Process Reference Year (1985)
    ref_cfg = CFG['assets']['reference']
    print(f">> Analyzing Reference Year: {ref_cfg['year']}")
    
    ndvi_ref = load_ndvi(ref_cfg['path'], AOI)
    ref_p2, ref_p98 = get_percentiles(ndvi_ref, ref_cfg['scale'], AOI)
    print("   Reference stats calculated (Lazy evaluation).")

    # 2. Process Target Years
    for target in CFG['assets']['targets']:
        year = target['year']
        print(f">> Processing Target Year: {year}")
        
        # Load
        ndvi_target = load_ndvi(target['path'], AOI)
        
        # Harmonize
        ndvi_harmonized = harmonize_image(ndvi_target, target['scale'], ref_p2, ref_p98, AOI)
        
        # Export
        export_to_drive(ndvi_harmonized, year, target['scale'], CFG['export_folder'], AOI)

    print(">> All tasks submitted to GEE.")

if __name__ == "__main__":
    main()