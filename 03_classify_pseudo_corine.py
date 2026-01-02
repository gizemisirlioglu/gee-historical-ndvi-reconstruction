"""
03_classify_pseudo_corine.py

Description:
    Generates historical "Pseudo-CORINE" Land Cover maps (1975, 1980, 1985) using 
    a Random Forest classifier trained on 1990 data.

Usage:
    python 03_classify_pseudo_corine.py --config config.json

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
# 2. GEE PROCESSING FUNCTIONS
# ==============================================================================

def load_singleband(asset_id, name, aoi):
    """Loads image, ensures float, single band, and clips."""
    img = ee.Image(asset_id).toFloat()
    img = ee.Image(ee.Algorithms.If(img.bandNames().length().gt(1), img.select([0]), img))
    return img.rename(name).clip(aoi)

def get_predictors(year, config, aoi, mean90, std90):
    """Constructs the feature stack (NDVI, Topo, Lat/Lon)."""
    # 1. NDVI & Z-Score
    year_str = str(year)
    ndvi_path = config['ndvi_assets'][year_str]
    ndvi = load_singleband(ndvi_path, "NDVI", aoi)
    ndvi_z = ndvi.subtract(mean90).divide(std90).rename("NDVI_z90")
    
    # 2. Topography
    dem = ee.Image("USGS/SRTMGL1_003").clip(aoi)
    elev = dem.rename("elev").toFloat()
    slope = ee.Terrain.slope(elev).rename("slope").toFloat()
    
    # 3. Coordinates
    coords = ee.Image.pixelLonLat().select(['latitude', 'longitude']).rename(['lat', 'lon']).toFloat()
    
    return ndvi.addBands(ndvi_z).addBands(elev).addBands(slope).addBands(coords)

def build_temporal_prior(config, aoi):
    """Constructs weighted temporal prior from future CORINE maps."""
    prior_bands = []
    n_classes = config['parameters']['n_classes']
    
    # Pre-load all CORINE images
    c_assets = config['corine_assets']
    imgs = {y: ee.Image(path).toInt().clip(aoi) for y, path in c_assets.items()}
    
    for c in range(1, n_classes + 1):
        # Weights logic: 1990 (0.7) > 2000s (0.2) > 2010s (0.1)
        # Note: Keys in JSON are strings, so we access with string keys
        p1990 = imgs['1990'].eq(c)
        p2000s = imgs['2000'].eq(c).add(imgs['2006'].eq(c)).divide(2)
        p2010s = imgs['2012'].eq(c).add(imgs['2018'].eq(c)).divide(2)
        
        prob = p1990.multiply(0.7).add(p2000s.multiply(0.2)).add(p2010s.multiply(0.1))
        prior_bands.append(prob.rename(f"p{c}"))
        
    return ee.Image.cat(prior_bands)

def train_rf(config, aoi, mean90, std90):
    """Trains Random Forest on 1990 data."""
    preds90 = get_predictors(1990, config, aoi, mean90, std90)
    label90 = ee.Image(config['corine_assets']['1990']).rename("lc").toInt().clip(aoi)
    
    samples = label90.addBands(preds90).stratifiedSample(
        numPoints=config['parameters']['samples_per_class'] * config['parameters']['n_classes'],
        classBand="lc",
        region=aoi,
        scale=60,
        classValues=ee.List.sequence(1, config['parameters']['n_classes']),
        classPoints=ee.List.repeat(config['parameters']['samples_per_class'], config['parameters']['n_classes']),
        geometries=False,
        seed=config['parameters']['seed'],
        tileScale=8
    )
    
    features = ["NDVI", "NDVI_z90", "elev", "slope", "lat", "lon"]
    return ee.Classifier.smileRandomForest(
        numberOfTrees=config['parameters']['rf_trees'], 
        seed=config['parameters']['seed']
    ).train(samples, "lc", features)

def classify_year(year, config, aoi, rf, prior, mean90, std90):
    """Classifies a target year using RF + Temporal Prior Fusion."""
    preds = get_predictors(year, config, aoi, mean90, std90)
    
    # RF Probabilities (Array)
    rf_probs_array = preds.classify(rf.setOutputMode("MULTIPROBABILITY"))
    
    # Flatten Array to Bands (p1..p7)
    info = ee.Dictionary(rf.explain())
    classes = ee.List(info.get("classes"))
    flat_labels = classes.map(lambda c: ee.String("k").cat(ee.Number(c).format()))
    flat_probs = rf_probs_array.arrayFlatten([flat_labels])
    
    rf_bands = []
    n_classes = config['parameters']['n_classes']
    for c in range(1, n_classes + 1):
        c_str = ee.String("k").cat(ee.Number(c).format())
        band = ee.Image(ee.Algorithms.If(
            classes.contains(c), flat_probs.select(c_str), ee.Image.constant(0)
        )).rename(f"p{c}")
        rf_bands.append(band)
    
    rf_img = ee.Image.cat(rf_bands)
    
    # Fusion
    alpha = config['parameters']['prior_alpha']
    reinforcement = ee.Image.constant(alpha).add(prior.multiply(1.0 - alpha))
    fused = rf_img.multiply(reinforcement)
    
    # Argmax
    return fused.toArray().arrayArgmax().arrayGet([0]).add(1).toByte().clip(aoi).rename("lc")

def post_process(img, min_size):
    """Smoothing and MMU."""
    cleaned = img.focal_mode(radius=1, units="pixels")
    conn = cleaned.connectedPixelCount(maxSize=100, eightConnected=True)
    cleaned = cleaned.updateMask(conn.gte(min_size)).unmask(cleaned)
    return cleaned.focal_mode(radius=1, units="pixels")

# ==============================================================================
# 3. MAIN EXECUTION
# ==============================================================================

def main():
    # Parse Command Line Arguments
    parser = argparse.ArgumentParser(description="Pseudo-CORINE Classifier")
    parser.add_argument('--config', type=str, default='config.json', help="Path to config file")
    args = parser.parse_args()
    
    # Load Config
    print(f">> Loading configuration from {args.config}...")
    CFG = load_config(args.config)
    
    # Init GEE
    init_gee(CFG['project_id'])
    AOI = ee.FeatureCollection(CFG['aoi_asset']).geometry()
    
    # 1. Statistics (1990)
    print(">> Calculating 1990 Stats...")
    ndvi90 = load_singleband(CFG['ndvi_assets']['1990'], "NDVI", AOI)
    stats = ndvi90.reduceRegion(ee.Reducer.mean().combine(ee.Reducer.stdDev(), "", True), AOI, 120)
    mean90 = ee.Number(stats.get("NDVI_mean"))
    std90 = ee.Number(stats.get("NDVI_stdDev")).max(1e-6)
    
    # 2. Train
    print(">> Training Random Forest...")
    rf_model = train_rf(CFG, AOI, mean90, std90)
    
    # 3. Prior
    print(">> Building Priors...")
    prior = build_temporal_prior(CFG, AOI)
    
    # 4. Classify Loop
    target_years = [1975, 1980, 1985]
    for year in target_years:
        print(f">> Processing {year}...")
        scale = CFG['export_scales']['tm'] if year >= 1984 else CFG['export_scales']['mss']
        
        raw = classify_year(year, CFG, AOI, rf_model, prior, mean90, std90)
        final = post_process(raw, CFG['parameters']['min_patch_size'])
        
        # Export
        name = f"Pseudo_CORINE_{year}_V3"
        task = ee.batch.Export.image.toDrive(
            image=final,
            description=name,
            folder=CFG['export_folder'],
            fileNamePrefix=name,
            region=AOI,
            scale=scale,
            maxPixels=1e13
        )
        task.start()
        print(f"   [Task Started] {name} -> Drive")

if __name__ == "__main__":
    main()