# gee-historical-ndvi-reconstruction
01-01_generate_historical_ndvi.js
# Historical Landsat NDVI Composite Generator (GEE)

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
