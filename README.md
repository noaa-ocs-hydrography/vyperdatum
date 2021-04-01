# Vyperdatum

Python module that drives PROJ to use VDatum grids in a simple and clear way.  Requires that VDatum be installed already (you can find VDatum [here](https://vdatum.noaa.gov/).  Developed in Python3.

VDatum is "a free software tool being developed jointly by NOAA's [National Geodetic Survey (NGS)](https://www.ngs.noaa.gov/), [Office of Coast Survey (OCS)](https://nauticalcharts.noaa.gov/), and [Center for Operational Oceanographic Products and Services (CO-OPS)](https://tidesandcurrents.noaa.gov/)...to vertically transform geospatial data among a variety of tidal, orthometric and ellipsoidal vertical datums".

Vyperdatum allows for VDatum to be used in production bathymetric processing software in a clean and precise way.  In addition, Vyperdatum builds a custom Compound and Vertical CRS object that well documents the resulting transformation, so that the inverse transformation can be accurately applied later to get back to the pivot datum (NAD83(2011)/EPSG:6319.

## Quickstart

Vyperdatum offers to main classes:

 - VyperPoints - for transforming 2d/3d point datasets
 - VyperRaster - for transforming GDAL supported raster datasets

For either of these objects, the first run needs to set the path to the VDatum installation in order for Vyperdatum to initialize properly:

    from vyperdatum.points import VyperPoints
    vp = VyperPoints(vdatum_directory='path/to/vdatum')

From there it is simple to start performing transformations.  Use the following examples to get started:

-- we assume vdatum_directory has already been set in these examples -- 

- Basic vertical transformation from NAD83 height to MLLW

        vp = VyperPoints()
        x = np.array([-76.19698, -76.194, -76.198])
        y = np.array([37.1299, 37.1399, 37.1499])
        z = np.array([10.5, 11.0, 11.5])
        
        # source ('nad83') = nad83(2011)/nad83(2011)height
        # destination ('mllw') = nad83/mllw
        vp.transform_points('nad83', 'mllw', x, y, z=z)
        
        vp.x
        Out: array([-76.19698, -76.194  , -76.198  ])
        vp.y
        Out: array([37.1299, 37.1399, 37.1499])
        vp.z
        Out: array([47.505, 47.987, 48.454])
        vp.unc
        Out: array([0.066, 0.066, 0.066])
        
        print(vp.out_crs.to_pretty_wkt())
        
        VERTCRS["mllw",
          VDATUM["mllw"],
          CS[vertical,1],
               AXIS["gravity-related height (H)",up],
               LENGTHUNIT["metre",1]]
          REMARK["regions=[MDVAchb12_8301],
                  pipeline=proj=pipeline step proj=vgridshift grids=core\geoid12b\g2012bu0.gtx step proj=vgridshift grids=REGION\tss.gtx step proj=vgridshift grids=REGION\mllw.gtx"]]
        


- 3d Transformation from EPSG:3631(NC StatePlane)/MLLW to NAD83/MLLW. 

        vp = VyperPoints()
        x = np.array([898745.505, 898736.854, 898728.203])
        y = np.array([256015.372, 256003.991, 255992.610])
        z = np.array([10.5, 11.0, 11.5])
        
        # force vertical datum used here to indicate source is at vert=mllw
        vp.transform_points(3631, 'mllw', x, y, z=z, force_input_vertical_datum='mllw')
        
        vp.x
        Out: array([-75.7918, -75.7919, -75.792 ])
        vp.y
        Out: array([36.0157, 36.0156, 36.0155])
        vp.z
        Out: array([10.5, 11. , 11.5])
        vp.unc
        Out: array([0.065, 0.065, 0.065])

- GeoTIFF transformation of source GeoTIFF with (horizontal=EPSG:26919, vertical=NAD83(2011) height) to EPSG:26919/MLLW 

        new_file = r"C:\data\tiff\output.tiff"
        test_file = r"C:\data\tiff\test.tiff"
        
        # source EPSG:26919 read automatically, NAD83 height assumed
        vr = VyperRaster(test_file, is_height=True)
        
        layers, layernames, layernodata = vr.transform_raster('mllw', 100, allow_points_outside_coverage=False, output_file=output_file)
        
        print(vr.out_crs.to_compound_wkt())
         
         COMPOUNDCRS["NAD83 / UTM zone 19N + mllw",
              PROJCS["NAD83 / UTM zone 19N",
                 GEOGCS["NAD83",DATUM["North_American_Datum_1983",
                    SPHEROID["GRS 1980",6378137,298.257222101,AUTHORITY["EPSG","7019"]],
                    AUTHORITY["EPSG","6269"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],
                    UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4269"]],
                    PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],
                    PARAMETER["central_meridian",-69],PARAMETER["scale_factor",0.9996],
                    PARAMETER["false_easting",500000],PARAMETER["false_northing",0],
                    UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],
                AUTHORITY["EPSG","26919"]],
              VERTCRS["mllw",
                VDATUM["mllw"],
                CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1],
                REMARK["regions=[MENHMAgome23_8301],
                       'pipeline=proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx
                                               step proj=vgridshift grids=REGION\\tss.gtx
                                               step proj=vgridshift grids=REGION\\mllw.gtx"]]]

 - GeoTIFF transformation with explicit input vertical datum
 
        new_file = r"C:\data\tiff\output.tiff"
        test_file = r"C:\data\tiff\test.tiff"
        
        # source EPSG:26919 read automatically, NAD83 height assumed
        vr = VyperRaster(test_file, is_height=True)
        
        layers, layernames, layernodata = vr.transform_raster('mllw', 100, allow_points_outside_coverage=False, 
                                                              force_input_vertical_datum='navd88', output_file=output_file) 