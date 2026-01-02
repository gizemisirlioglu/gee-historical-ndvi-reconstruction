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

### Usage
1. Ensure you have the Google Earth Engine Python API installed:
   ```bash
   pip install earthengine-api
