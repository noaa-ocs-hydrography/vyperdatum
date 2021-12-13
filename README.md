# Vyperdatum

Python module that drives PROJ to use VDatum grids in a simple and clear way.  Requires that VDatum be installed already (you can find VDatum [here](https://vdatum.noaa.gov/).  Developed in Python3.

VDatum is "a free software tool being developed jointly by NOAA's [National Geodetic Survey (NGS)](https://www.ngs.noaa.gov/), [Office of Coast Survey (OCS)](https://nauticalcharts.noaa.gov/), and [Center for Operational Oceanographic Products and Services (CO-OPS)](https://tidesandcurrents.noaa.gov/)...to vertically transform geospatial data among a variety of tidal, orthometric and ellipsoidal vertical datums".

Vyperdatum allows for VDatum to be used in production bathymetric processing software in a clean and precise way.  In addition, Vyperdatum builds a custom Compound and Vertical CRS object that well documents the resulting transformation, so that the inverse transformation can be accurately applied later to get back to the pivot datum (NAD83(2011)/EPSG:6319.

## Installation

Vyperdatum is not on PyPi, but can be installed using pip.

(For Windows Users) Download and install Visual Studio Build Tools 2019 (If you have not already): [MSVC Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)

Download and install conda (If you have not already): [conda installation](https://docs.conda.io/projects/conda/en/latest/user-guide/install/)

Download and install git (If you have not already): [git installation](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

Some dependencies need to be installed from the conda-forge channel.  I have an example below of how to build this environment using conda.

Perform these in order:

`conda create -n vyper python=3.8.8 `

`conda activate vyper `

`conda install -c conda-forge gdal=3.2.1`

`pip install git+https://github.com/noaa-ocs-hydrography/vyperdatum.git#egg=vyperdatum `

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
        
        vp.transform_points(6319, 'mllw', x, y, z=z)
        # this is a shortcut for vp.transform_points((6319, 'ellipse'), 'mllw', x, y, z=z)
        
        vp.x
        Out: array([-76.19698, -76.194  , -76.198  ])
        vp.y
        Out: array([37.1299, 37.1399, 37.1499])
        vp.z
        Out: array([47.735, 48.219, 48.685])
        vp.unc
        Out: array([0.115, 0.115, 0.115])
        
        print(vp.out_crs.to_wkt())
        
        COMPOUNDCRS["NAD83(2011) + mllw",
          GEOGCRS["NAD83(2011)",
            DATUM["NAD83 (National Spatial Reference System 2011)",
              ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],
              PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],
              CS[ellipsoidal,2],
                AXIS["geodetic latitude (Lat)",north,ORDER[1],ANGLEUNIT["degree",0.0174532925199433]],
                AXIS["geodetic longitude (Lon)",east,ORDER[2],ANGLEUNIT["degree",0.0174532925199433]],
                USAGE[SCOPE["Horizontal component of 3D system."],
                AREA["Puerto Rico - onshore and offshore. United States (USA) onshore and offshore - Alabama; Alaska; Arizona; Arkansas; California; Colorado; Connecticut; Delaware; Florida; Georgia; Idaho; Illinois; Indiana; Iowa; Kansas; Kentucky; Louisiana; Maine; Maryland; Massachusetts; Michigan; Minnesota; Mississippi; Missouri; Montana; Nebraska; Nevada; New Hampshire; New Jersey; New Mexico; New York; North Carolina; North Dakota; Ohio; Oklahoma; Oregon; Pennsylvania; Rhode Island; South Carolina; South Dakota; Tennessee; Texas; Utah; Vermont; Virginia; Washington; West Virginia; Wisconsin; Wyoming. US Virgin Islands - onshore and offshore."],
                BBOX[14.92,167.65,74.71,-63.88]],ID["EPSG",6318]],
          VERTCRS["mllw",
            VDATUM["mllw"],
              CS[vertical,1],
                AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],
                REMARK["vdatum=vdatum_4.1.2_20201203,vyperdatum=0.1.6,base_datum=[NAD83(2011)],
                        regions=[MDVAchb12_8301],
                        pipelines=[+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=MDVAchb12_8301\\tss.gtx +step +proj=vgridshift grids=MDVAchb12_8301\\mllw.gtx]"]]]'        

- 3d Transformation from EPSG:3631(NC StatePlane)/MLLW to NAD83/MLLW. 

        vp = VyperPoints()
        x = np.array([898745.505, 898736.854, 898728.203])
        y = np.array([256015.372, 256003.991, 255992.610])
        z = np.array([10.5, 11.0, 11.5])
        
        # here we use input horizontal/vertical datums for both input and output datum
        vp.transform_points((3631, 'mllw'), (6319, 'mllw'), x, y, z=z)
        
        vp.x
        Out: array([-75.7918, -75.7919, -75.792 ])
        vp.y
        Out: array([36.0157, 36.0156, 36.0155])
        vp.z
        Out: array([10.5, 11. , 11.5])
        vp.unc
        Out: array([0.028, 0.028, 0.028])

- GeoTIFF transformation - GeoTIFF with horizontal=EPSG:26919, vertical=NAD83(2011) height (assumed) to EPSG:26919/MLLW.  
        
        from vyperdatum.raster import VyperRaster
        
        new_file = r"C:\data\tiff\output.tiff"
        test_file = r"C:\data\tiff\test.tiff"
        
        # source EPSG:26919 read automatically, NAD83 height assumed
        vr = VyperRaster(test_file)
        
        # optional step saying the raster is at horiz=26919, vert=ellipse
        # vr.set_input_datum(26919, 'ellipse')
        
        # output=mllw input=ellipse
        layers, layernames, layernodata = vr.transform_raster('mllw', 'ellipse', allow_points_outside_coverage=True, output_filename=new_file)
        
        print(vr.out_crs.to_compound_wkt())
         
        COMPOUNDCRS["NAD83 / UTM zone 19N + mllw",
          PROJCRS["NAD83 / UTM zone 19N",
            BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],
              PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],
                CONVERSION["UTM zone 19N",METHOD["Transverse Mercator",ID["EPSG",9807]],
                  PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],
                  PARAMETER["Longitude of natural origin",-69,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],
                  PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],
                  PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],
                  PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],
                    AXIS["easting",east,ORDER[1],LENGTHUNIT["metre",1]],
                    AXIS["northing",north,ORDER[2],LENGTHUNIT["metre",1]],ID["EPSG",26919]],
          VERTCRS["mllw",
            VDATUM["mllw"],
              CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],
              REMARK["vdatum=vdatum_4.1.2_20201203,vyperdatum=0.1.6,base_datum=[NAD83(2011)],
                      regions=[MENHMAgome23_8301],
                      pipelines=[+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=MENHMAgome23_8301\\tss.gtx +step +proj=vgridshift grids=MENHMAgome23_8301\\mllw.gtx]"]]]'
