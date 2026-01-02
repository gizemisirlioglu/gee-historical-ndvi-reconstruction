# gee-historical-ndvi-reconstruction

#  1. Historical Landsat NDVI Composite Generator (GEE)

This repository contains a Google Earth Engine (JavaScript) script designed to reconstruct historical Normalized Difference Vegetation Index (NDVI) time-series data using **Landsat MSS (1-3)** and **Landsat TM (5)** sensors.

It focuses on generating "Greenest Pixel" composites (using `qualityMosaic`) for the summer season to minimize cloud cover and phenological variations in long-term studies.

## Features
- **Multi-Sensor Support:** Handles band differences between Landsat MSS and TM automatically.
- **Configurable:** Users can easily set their Area of Interest (AOI), years, and export resolution.
- **Max NDVI Compositing:** Uses the `qualityMosaic()` method to capture peak vegetation.

## Usage

1. Open the script `generate_ndvi_composites.js` in the Google Earth Engine Code Editor.
2. Edit the **USER CONFIGURATION** section at the top of the script:
   ```javascript
   var CONFIG = {
     aoiAssetPath: 'users/YOUR_USERNAME/your_study_area',
     outputAssetFolder: 'users/YOUR_USERNAME/results_folder',
     // ...
   };
## 2. Radiometric Harmonization (Python)

After generating the raw composites in Step 1, the `02_harmonize_ndvi_time_series.py` script harmonizes the older Landsat MSS data (1975, 1980) to match the radiometric distribution of the Landsat TM reference year (1985).

### Methodology
It uses a **Percentile Mapping** approach:
1. Calculates the 2nd ($P_{2}$) and 98th ($P_{98}$) percentiles for the reference image (1985).
2. Rescales the target images (1975, 1980) so that their $P_{2}$ and $P_{98}$ match the reference year.
3. Clamps values to the valid NDVI range $[-1, 1]$.

### Configuration
All settings are managed via the `02_config_harmonize.json` file.

1. Open `config_harmonize.json`.
2. Update `project_id` and `aoi_asset` to match your GEE environment.
3. Define your input paths in the `assets` section (Reference year vs Target years).

### Usage
1. Ensure you have the Google Earth Engine Python API installed:
   ```bash
   pip install earthengine-api
   
## 3. Pseudo-CORINE Classification (Python)

The core script `03_classify_pseudo_corine.py` generates the historical land cover maps for 1975, 1980, and 1985. It employs a **Back-casting** strategy, where a model trained on the stable 1990 CORINE baseline is applied to the harmonized historical imagery.

### Methodology
1. **Feature Engineering:** Constructs a predictor stack using harmonized NDVI, Z-scores (relative to 1990), Topographic variables (SRTM Elevation & Slope), and Spatial coordinates (Lat/Lon).
2. **Random Forest Classification:** Trains a classifier using the 1990 Official CORINE dataset as ground truth.
3. **Temporal Fusion:** Integrates the Random Forest probabilities with a weighted **Temporal Prior** (derived from 1990–2018 trends). This step stabilizes the classification in spectrally ambiguous areas.
4. **Post-Processing:** Applies spatial smoothing and connectivity checks to enforce a Minimum Mapping Unit (MMU) consistent with CORINE standards (~9 pixels).

### Configuration
All settings are managed via the `config_classify.json` file.

1. Open `config_classify.json`.
2. Update `project_id` and `aoi_asset` to match your GEE environment.
3. Ensure the `ndvi_assets` paths point to the **harmonized** outputs generated in Step 2.
4. (Optional) You can tune parameters such as `rf_trees` (default: 300) or `prior_alpha` (fusion weight) in the `parameters` section.

### Usage
Run the script passing the configuration file:

```bash
python 03_classify_pseudo_corine.py --config 03_config_classify.json
