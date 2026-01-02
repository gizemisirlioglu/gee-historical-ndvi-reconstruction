"""
04_export_transition_stats.py

Description:
    Calculates pixel-based transition matrices between land cover pairs and 
    exports the frequency histograms to Google Drive as CSV files. 
    Also performs a quick Quality Control (QC) check for illogical transitions.

Usage:
    python 04_export_transition_stats.py --config config_transitions.json

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
    if not os.path.exists(config_path):
        print(f"ERROR: Config file '{config_path}' not found.")
        sys.exit(1)
    with open(config_path, 'r') as f:
        return json.load(f)

def init_gee(project_id):
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

def load_lc(asset_id, n_classes, aoi):
    """Loads a land cover image, masks invalid classes, and clips."""
    img = ee.Image(asset_id).toInt()
    # Mask values outside 1..N range
    img = img.updateMask(img.gte(1).And(img.lte(n_classes)))
    return img.clip(aoi)

def export_transition_histogram(year1, year2, config, aoi):
    """Calculates transition counts and starts a CSV export task."""
    path1 = config['assets'][str(year1)]
    path2 = config['assets'][str(year2)]
    
    img1 = load_lc(path1, config['n_classes'], aoi).rename("from")
    img2 = load_lc(path2, config['n_classes'], aoi).rename("to")
    
    # Create transition code: 100 * class_from + class_to (e.g. 1 -> 2 becomes 102)
    trans_img = img1.multiply(100).add(img2).rename("transition")
    
    # Calculate Histogram
    hist = trans_img.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=aoi,
        scale=config['scale'],
        maxPixels=1e13,
        bestEffort=True
    )
    
    # Format for CSV export
    raw_dict = ee.Dictionary(hist.get("transition"))
    keys = raw_dict.keys()
    
    feature_col = ee.FeatureCollection(keys.map(lambda k: ee.Feature(None, {
        "transition_code": ee.Number.parse(ee.String(k)),
        "pixel_count": ee.Number(raw_dict.get(k)),
        "from_year": year1,
        "to_year": year2
    })))
    
    desc = f"Transition_Stats_{year1}_{year2}"
    task = ee.batch.Export.table.toDrive(
        collection=feature_col,
        description=desc,
        folder=config['export_folder'],
        fileNamePrefix=desc,
        fileFormat="CSV"
    )
    task.start()
    print(f"   [Task Started] {desc} -> Drive/{config['export_folder']}")

def check_improbable_transitions(year1, year2, config, aoi):
    """Prints the percentage of ecologically unlikely transitions (QC)."""
    path1 = config['assets'][str(year1)]
    path2 = config['assets'][str(year2)]
    
    a = load_lc(path1, config['n_classes'], aoi)
    b = load_lc(path2, config['n_classes'], aoi)

    # Define illogical rules (customize as needed)
    # 1. Forest (3,4,5) -> Artificial (1)
    forest_to_urban = (a.gte(3).And(a.lte(5))).And(b.eq(1))
    
    # 2. Wetland (6) <-> Artificial (1)
    wet_to_urban = a.eq(6).And(b.eq(1))
    urban_to_wet = a.eq(1).And(b.eq(6))
    
    # 3. Wetland (6) -> Forest (3,4,5) (Rapid drying is rare)
    wet_to_forest = a.eq(6).And(b.gte(3).And(b.lte(5)))

    bad_pixels = forest_to_urban.Or(wet_to_urban).Or(urban_to_wet).Or(wet_to_forest)
    
    # Count pixels
    bad_count = bad_pixels.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=aoi,
        scale=config['scale'],
        maxPixels=1e13,
        bestEffort=True
    ).get(bad_pixels.bandNames().get(0))
    
    total_count = a.reduceRegion(
        reducer=ee.Reducer.count(),
        geometry=aoi,
        scale=config['scale'],
        maxPixels=1e13,
        bestEffort=True
    ).get(a.bandNames().get(0))
    
    # Calculate percentage locally (Client-side)
    bad_val = ee.Number(bad_count).getInfo()
    tot_val = ee.Number(total_count).getInfo()
    
    if tot_val > 0:
        ratio = (bad_val / tot_val) * 100
        print(f"   QC {year1}->{year2}: Improbable transitions = {ratio:.3f}%")
    else:
        print(f"   QC {year1}->{year2}: No data found.")

# ==============================================================================
# 3. MAIN EXECUTION
# ==============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config_transitions.json')
    args = parser.parse_args()
    
    print(f">> Loading config: {args.config}")
    CFG = load_config(args.config)
    
    init_gee(CFG['project_id'])
    AOI = ee.FeatureCollection(CFG['aoi_asset']).geometry()
    
    print(">> Starting Transition Analysis...")
    
    for pair in CFG['pairs']:
        y1, y2 = pair
        print(f">> Processing Pair: {y1} - {y2}")
        
        # 1. Export CSV
        export_transition_histogram(y1, y2, CFG, AOI)
        
        # 2. Quick QC
        check_improbable_transitions(y1, y2, CFG, AOI)
        
    print(">> All export tasks submitted.")

if __name__ == "__main__":
    main()