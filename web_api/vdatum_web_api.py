try:  # python27
    import urllib2
except ImportError:  # python38
    from urllib.request import Request, urlopen
import json
import time


def vdatum_web_api(src_lat, src_lon, src_height, region='CONTIGUOUS', s_h_frame='NAD83_2011', s_v_frame='MLLW',
                   t_h_frame='NAD83_2011', t_v_frame='NAVD88'):
    """
    https://vdatum.noaa.gov/docs/services.html

    Run under python27, using the urllib2 module

    Parameters
    ----------
    src_lon: Source Longitude
    src_lat: Source Latitude
    src_height: Source Height
    s_h_frame: Input Source Horizontal Reference Frame
    s_v_frame: Input Source Vertical Reference Frame
    t_h_frame: Input Target Horizontal Reference Frame
    t_v_frame: Input Target Tidal Datum, or NAVD88, or NAD83_2011
    
    Returns
    -------
    tar_lon: Target Longitude
    tar_lat: Target Latitude.
    tar_height: Result Target Height
    """

    url = 'https://vdatum.noaa.gov/vdatumweb/api/tidal?lon=%s&lat=%s&height=%s&region=%s&s_h_frame=%s&s_v_frame=%s&t_h_frame=%s&t_v_frame=%s' \
           %(src_lat, src_lon, src_height, region, s_h_frame, s_v_frame, t_h_frame, t_v_frame)

    print(url)
    try:
        request = urllib2.Request(url)
        response = urllib2.urlopen(request, timeout=20).read()
    except:
        request = Request(url)
        response = urlopen(request, timeout=20).read()
    data = json.loads(response)
    return (float(data['tar_lon']), float(data['tar_lat']), float(data['tar_height']))


if __name__ == '__main__':
    # expected output
    tx = -70.7
    ty = 43
    tz = -1.547
    # input values
    xx = -70.7
    yy = 43
    zz = 0
    print('input:', (xx, yy, zz))
    try:
        start_time = time.time()
        result = vdatum_web_api(xx, yy, zz, s_v_frame='MLLW', t_v_frame='NAVD88')
        print('run time for one web query is %.10f(s)' %(time.time() - start_time))
    except:
        print('error')
    print('output:', result)

    try:
        assert tx == result[0]
    except AssertionError:
        print ('Expected X value was not produced')
    try:
        assert ty == result[1]
    except AssertionError:
        print ('Expected Y value was not produced')
    try:
        assert tz == result[2]
    except AssertionError:
        print ('Expected Z value was not produced')
