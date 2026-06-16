import hashlib
import json
import logging
import os
import requests
import time

logger = logging.getLogger(__name__)

SODA_DOMAIN = 'www.datos.gov.co'
DATASET_ID = '79dd-d24f'
LIMIT_PER_PAGE = 50000
CACHE_FILE = '/tmp/records_cache.json'
GEOJSON_URL = 'https://raw.githubusercontent.com/andresmtr/mapa_municipios_colombia_geojonson/master/co_2018_MGN_MPIO_POLITICO_AT.geojson'
GEOJSON_CACHE = '/tmp/municipios_geojson_cache.json'

# Correct department centroids for fallback
DEPT_COORDS = {
    '05': [6.5,-75.5], '08': [10.5,-74.9], '11': [4.6,-74.1], '13': [10.0,-75.0],
    '15': [5.5,-73.0], '17': [5.0,-75.5], '18': [1.5,-75.0], '19': [5.5,-71.5],
    '20': [2.5,-76.5], '23': [9.5,-73.5], '25': [4.5,-74.0], '27': [6.5,-76.5],
    '41': [2.5,-69.0], '44': [11.0,-72.5], '47': [10.5,-74.5], '50': [4.0,-72.5],
    '52': [1.5,-78.0], '54': [8.0,-72.5], '63': [4.5,-75.5], '66': [5.0,-75.5],
    '68': [6.5,-73.5], '70': [9.5,-75.5], '73': [4.0,-75.0], '76': [3.5,-76.5],
    '81': [7.0,-70.5], '85': [5.5,-71.5], '86': [0.5,-76.5], '88': [12.5,-81.5],
    '91': [-1.5,-71.5], '94': [2.5,-72.5], '95': [2.5,-69.0], '97': [5.0,-69.0],
    '99': [5.0,-69.0],
}


def _fetch_all_from_api():
    base_url = f'https://{SODA_DOMAIN}/resource/{DATASET_ID}.json'
    all_data = []
    offset = 0
    while True:
        url = f'{base_url}?$limit={LIMIT_PER_PAGE}&$offset={offset}'
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_data.extend(batch)
        if len(batch) < LIMIT_PER_PAGE:
            break
        offset += LIMIT_PER_PAGE
    return all_data


def get_records(force_refresh=False):
    if not force_refresh and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    records = _fetch_all_from_api()
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False)
    return records


YEAR_FIELD = 'a_o_del_hecho'


def resolve_record(r, geo_lookup):
    try:
        mun_code = int(r.get('codigo_dane_municipio') or '0')
    except (ValueError, TypeError):
        mun_code = 0
    info = geo_lookup.get(mun_code, {})
    dept_name = info.get('dept_name') or r.get('departamento_del_hecho_dane') or 'Sin info'
    dept_code = info.get('dept_code') or r.get('codigo_dane_departamento') or '00'
    mun_name = info.get('name') or r.get('municipio_del_hecho_dane') or 'Sin info'
    return {
        'dept_name': dept_name,
        'dept_code': dept_code,
        'mun_name': mun_name,
        'mun_code': str(mun_code) if mun_code else (r.get('codigo_dane_municipio') or '00000'),
        'lat': info.get('lat', 4.0),
        'lng': info.get('lng', -74.0),
    }


def _polygon_centroid(coords):
    xs, ys, n = 0, 0, 0
    for ring in coords:
        for pt in ring:
            xs += pt[0]
            ys += pt[1]
            n += 1
    return (ys / n, xs / n) if n else (4.0, -74.0)


def _load_geojson():
    geojson = None
    for attempt in range(3):
        try:
            logger.info('Downloading municipality GeoJSON from %s (attempt %d)', GEOJSON_URL, attempt+1)
            resp = requests.get(GEOJSON_URL, timeout=600)
            resp.raise_for_status()
            geojson = resp.json()
            logger.info('GeoJSON downloaded successfully (%d bytes)', len(resp.content))
            break
        except Exception as e:
            logger.warning('Attempt %d failed: %s', attempt+1, e)
            if attempt < 2:
                time.sleep(5 * (attempt+1))
    if geojson is None:
        logger.warning('All GeoJSON download attempts failed.')
        return None

    result = {}
    for feat in geojson.get('features', []):
        props = feat.get('properties', {})
        try:
            code = int(props.get('MPIO_CCNCT') or 0)
        except (ValueError, TypeError):
            continue
        if code == 0:
            continue
        name = (props.get('MPIO_CNMBR') or '').strip()
        dept_code = str(props.get('DPTO_CCDGO') or '').strip()
        dept_name = (props.get('DPTO_CNMBR') or '').strip()
        geom = feat.get('geometry', {})
        try:
            if geom.get('type') == 'Polygon':
                coords = geom.get('coordinates', [])
                lat, lng = _polygon_centroid(coords)
            elif geom.get('type') == 'MultiPolygon':
                all_coords = []
                for poly in geom.get('coordinates', []):
                    all_coords.extend(poly)
                lat, lng = _polygon_centroid(all_coords)
            else:
                lat, lng = 4.0, -74.0
        except Exception:
            dept_center = DEPT_COORDS.get(dept_code, [4.0, -74.0])
            h = int(hashlib.md5(str(code).encode()).hexdigest()[:8], 16) % 10000
            lat = dept_center[0] + (h % 100 - 50) * 0.01
            lng = dept_center[1] + ((h // 100) % 100 - 50) * 0.01
        result[code] = {
            'name': name,
            'dept_code': dept_code,
            'dept_name': dept_name,
            'lat': lat,
            'lng': lng,
        }

    logger.info('Generated %d municipality entries from GeoJSON', len(result))
    if len(result) < 100:
        logger.warning('Only %d municipalities found in GeoJSON.', len(result))
        return None

    with open(GEOJSON_CACHE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)
    return result


def get_municipio_coords(force_refresh=False):
    if not force_refresh and os.path.exists(GEOJSON_CACHE):
        size = os.path.getsize(GEOJSON_CACHE)
        if size > 1000:
            with open(GEOJSON_CACHE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data:
                return {int(k): v for k, v in data.items()}
    geojson_data = _load_geojson()
    if geojson_data is not None:
        return geojson_data
    return _generate_fallback_coords()


def _generate_fallback_coords():
    result = {}
    for code_5, center in DEPT_COORDS.items():
        for mun_suffix in range(1, 200):
            mun_code_str = code_5 + str(mun_suffix).zfill(3)
            try:
                mun_code = int(mun_code_str)
            except ValueError:
                continue
            h = int(hashlib.md5(mun_code_str.encode()).hexdigest()[:8], 16) % 10000
            lat = center[0] + (h % 100 - 50) * 0.008
            lng = center[1] + ((h // 100) % 100 - 50) * 0.008
            result[mun_code] = {
                'name': f'Municipio {mun_suffix}',
                'dept_code': code_5,
                'dept_name': f'Departamento {code_5}',
                'lat': lat,
                'lng': lng,
            }
    with open(GEOJSON_CACHE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)
    logger.info('Generated %d fallback municipality entries', len(result))
    return result
