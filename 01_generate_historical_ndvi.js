/**
 * @name Landsat Summer NDVI Composite Generator
 * @description Generates summer NDVI composites (max NDVI / qualityMosaic) for Landsat MSS and TM sensors.
 * Exports the results to Google Earth Engine Assets.
 * @author [Adın Soyadın]
 * @license MIT
 */

// ============================================================================
// 1. USER CONFIGURATION (EDIT THIS SECTION)
// ============================================================================

var CONFIG = {
  // ----------------- PATHS -----------------
  // Path to your Area of Interest (FeatureCollection)
  // Example: 'users/your_username/thesis/study_area'
  aoiAssetPath: 'users/username/path/to/AOI', 
  
  // Folder where the images will be exported
  // Example: 'users/your_username/assets'
  outputAssetFolder: 'users/username/path/to/assets', 

  // ----------------- DATES -----------------
  // Summer window definition
  summer: {
    startMonth: 6, // June
    startDay: 1,
    endMonth: 9,   // September
    endDay: 1
  },

  // ----------------- SCALES -----------------
  // Pixel resolution in meters
  scale: {
    mss: 180, // Coarser for MSS (approx 60m resampled)
    tm: 120   // For TM (approx 30m, but 120 used for harmonization consistency)
  },

  // ----------------- YEARS -----------------
  // Define which years and sensors to process
  periods: [
    { year: 1975, sensor: 'MSS' },
    { year: 1980, sensor: 'MSS' },
    { year: 1985, sensor: 'TM' },
    { year: 1990, sensor: 'TM' }
  ]
};

// ============================================================================
// 2. MAIN SCRIPT (DO NOT EDIT BELOW UNLESS CUSTOMIZING LOGIC)
// ============================================================================

// Load Area of Interest
var AOI = ee.FeatureCollection(CONFIG.aoiAssetPath).geometry();

/**
 * Creates an NDVI collection for a given year and sensor parameters.
 */
function makeNdviCollection(year, collectionId, nirBand, redBand) {
  var start = ee.Date.fromYMD(year, CONFIG.summer.startMonth, CONFIG.summer.startDay);
  var end   = ee.Date.fromYMD(year, CONFIG.summer.endMonth, CONFIG.summer.endDay);

  return ee.ImageCollection(collectionId)
    .filterDate(start, end)
    .filterBounds(AOI)
    .map(function(img) {
      img = img.clip(AOI);
      var nir  = img.select(nirBand);
      var red  = img.select(redBand);
      // Calculate NDVI: (NIR - Red) / (NIR + Red)
      var ndvi = nir.subtract(red).divide(nir.add(red)).rename('NDVI');
      
      // Return NDVI with original image properties (for metadata)
      return ndvi.copyProperties(img, img.propertyNames());
    });
}

/**
 * Builds a single summer NDVI composite using qualityMosaic (Max NDVI).
 */
function yearlyNdviComposite(year, sensor) {
  var col;

  if (sensor === 'MSS') {
    // Merge MSS collections (Landsat 2 and 3)
    col = ee.ImageCollection([])
      .merge(makeNdviCollection(year, 'LANDSAT/LM02/C02/T1', 'B7', 'B5'))
      .merge(makeNdviCollection(year, 'LANDSAT/LM03/C02/T1', 'B7', 'B5'));
  } else if (sensor === 'TM') {
    // Landsat 5 TM
    col = makeNdviCollection(year, 'LANDSAT/LT05/C02/T1_TOA', 'B4', 'B3');
  } else {
    throw new Error('Unknown sensor type: ' + sensor);
  }

  // Use qualityMosaic to find the "greenest" pixel (max NDVI) in the stack
  return col.qualityMosaic('NDVI').select('NDVI').clip(AOI);
}

/**
 * Exports the processed image to GEE Assets.
 */
function exportToAsset(img, year, sensor) {
  var exportScale = (sensor === 'MSS') ? CONFIG.scale.mss : CONFIG.scale.tm;
  var name = 'NDVI_SUMMER_' + year + '_clip';
  var assetId = CONFIG.outputAssetFolder + '/' + name;

  Export.image.toAsset({
    image: img,
    description: name,
    assetId: assetId,
    region: AOI,
    scale: exportScale,
    maxPixels: 1e13
  });

  print('Export task created for ' + year + ' (' + sensor + ') at ' + exportScale + 'm resolution.');
}

// ----------------- EXECUTION -----------------

print('Starting NDVI Composite Process...', CONFIG.periods);

CONFIG.periods.forEach(function(obj) {
  var ndvi = yearlyNdviComposite(obj.year, obj.sensor);
  exportToAsset(ndvi, obj.year, obj.sensor);
});

// Visualization for the last defined year (sanity check)
var lastRun = CONFIG.periods[CONFIG.periods.length - 1];
Map.centerObject(AOI, 8);
Map.addLayer(yearlyNdviComposite(lastRun.year, lastRun.sensor), 
             {min: -0.2, max: 0.8, palette: ['blue', 'white', 'green']}, 
             'Preview: NDVI ' + lastRun.year);