"""
02_harmonize_ndvi_time_series.py

Description:
    Harmonizes historical NDVI data (e.g., Landsat MSS) to a reference distribution 
    (e.g., Landsat TM) using a Percentile Mapping approach (P2-P98).
    
    This process minimizes sensor-based radiometric discrepancies, creating a 
    consistent time-series for long-term change detection.

Methodology:
    1. Calculate P2 (2nd percentile) and P98 (98th percentile) for the Reference Year (1985).
    2. Normalize historical years (1975, 1980) to their own P2-P98 range.
    3. Scale the normalized values to match the Reference P2-P98 range.
    4. Export the harmonized results to Google Drive.

Author: [Adın Soyadın]
License: MIT
"""

import ee

# ==============================================================================
# 1. USER CONFIGURATION
# ==============================================================================
CONFIG = {
    # GEE Project ID (Leave None to use default)
    'project_id': 'doktora-tezi-471512',
    
    # Path to your Area of Interest (FeatureCollection)
    'aoi_asset': 'projects/doktora-tezi-471512/assets/studyarea',
    
    # Folder name in your Google Drive where images will be exported
    'export_folder': 'GEE_NDVI_HARMONIZED',
    
    # Input Assets (Result of Step 01)
    'assets': {
        'reference': {
            'year': 1985,
            'path': 'projects/doktora-tezi-471512/assets/NDVI_1985',
            'scale': 120 # TM scale
        },
        'targets': [
            {
                'year': 1975,
                'path': 'projects/doktora-tezi-471512/assets/NDVI_1975_fixed_p2p98_-1to1',
                'scale': 180 # MSS scale
            },
            {
                'year': 1980,
                'path': 'projects/doktora-tezi-471512/assets/NDVI_1980_fixed_p2p98_-1to1',
                'scale': 180
            }
        ]
    }
}

# ==============================================================================
# 2. INITIALIZATION
# ==============================================================================
try:
    ee.Initialize(project=CONFIG['project_id'])
    print(f">> GEE Initialized successfully (Project: {CONFIG['project_id']})")
except Exception as e:
    print(">> GEE Authentication required. Authenticating...")
    ee.Authenticate()
    ee.Initialize(project=CONFIG['project_id'])

# Load AOI
AOI = ee.FeatureCollection(CONFIG['aoi_asset']).geometry()

# ==============================================================================
# 3. HELPER FUNCTIONS
# ==============================================================================

def load_ndvi(asset_id):
    """Loads a single-band NDVI image, ensures float type, and clips to AOI."""
    img = ee.Image(asset_id).toFloat()
    # If image has multiple bands, select the first one (assuming it is NDVI)
    img = ee.Image(ee.Algorithms.If(img.bandNames().length().gt(1), img.select([0]), img))
    return img.rename("NDVI").clip(AOI)

def get_percentiles(img, scale):
    """Computes the 2nd and 98th percentiles over the AOI."""
    stats = img.reduceRegion(
        reducer=ee.Reducer.percentile([2, 98]),
        geometry=AOI,
        scale=scale,
        bestEffort=True,
        maxPixels=1e13
    )
    p2  = ee.Number(stats.get("NDVI_p2"))
    # Ensure p98 is at least slightly larger than p2 to avoid division by zero
    p98 = ee.Number(stats.get("NDVI_p98")).max(p2.add(1e-6))
    return p2, p98

def harmonize_image(target_img, target_scale, ref_p2, ref_p98):
    """
    Applies percentile mapping to harmonize the target image to the reference distribution.
    Formula: New = [(Old - Old_P2) / (Old_P98 - Old_P2)] * (Ref_P98 - Ref_P2) + Ref_P2
    """
    # 1. Get statistics of the target image
    t_p2, t_p98 = get_percentiles(target_img, target_scale)
    
    # 2. Normalize target to 0-1 range based on its own P2-P98
    normalized = target_img.subtract(t_p2).divide(t_p98.subtract(t_p2))
    
    # 3. Scale to Reference P2-P98 range
    remapped = normalized.multiply(ref_p98.subtract(ref_p2)).add(ref_p2)
    
    # 4. Clamp to valid NDVI range [-1, 1] and reference bounds to remove outliers
    return remapped.clamp(ref_p2, ref_p98).clamp(-1, 1).rename("NDVI")

def export_to_drive(img, year, scale, folder):
    """Exports the processed image to Google Drive."""
    filename = f"NDVI_{year}_Harmonized_to_1985"
    
    task = ee.batch.Export.image.toDrive(
        image=img,
        description=filename,
        folder=folder,
        fileNamePrefix=filename,
        region=AOI,
        scale=scale,
        maxPixels=1e13
    )
    task.start()
    print(f"[EXPORT STARTED] {filename} -> Drive/{folder} (scale={scale}m)")

# ==============================================================================
# 4. MAIN EXECUTION
# ==============================================================================

def main():
    print(">> Starting Harmonization Process...")
    
    # 1. Process Reference Year (1985)
    print(f">> Analyzing Reference Year: {CONFIG['assets']['reference']['year']}")
    ref_asset = CONFIG['assets']['reference']
    ndvi_ref = load_ndvi(ref_asset['path'])
    
    # Calculate Reference Statistics
    ref_p2, ref_p98 = get_percentiles(ndvi_ref, ref_asset['scale'])
    print("   Reference stats calculated (Lazy evaluation).")

    # 2. Process Target Years (1975, 1980)
    for target in CONFIG['assets']['targets']:
        year = target['year']
        print(f">> Processing Target Year: {year}")
        
        # Load
        ndvi_target = load_ndvi(target['path'])
        
        # Harmonize
        ndvi_harmonized = harmonize_image(ndvi_target, target['scale'], ref_p2, ref_p98)
        
        # Export
        export_to_drive(ndvi_harmonized, year, target['scale'], CONFIG['export_folder'])

    print(">> All tasks submitted to GEE.")

if __name__ == "__main__":
    main()