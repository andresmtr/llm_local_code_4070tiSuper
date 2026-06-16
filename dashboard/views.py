import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from data_fetching_service import get_records, get_municipio_coords, resolve_record, YEAR_FIELD
from report_service import generate_report

MONTH_ORDER = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
MONTH_MAP = {m:i for i,m in enumerate(MONTH_ORDER)}


def _normalize(v):
    if not v:
        return 'Sin info'
    v = ' '.join(v.strip().split())
    if not v:
        return 'Sin info'
    lowered = v.lower()
    if lowered in ('no aplica', 'no aplica '):
        return 'No aplica'
    if lowered in ('no sabe / no informa', 'no sabe/no informa',
                   'no sabe /no informa', 'no sabe', 'no informa'):
        return 'No sabe / No informa'
    if lowered in ('sin info', 'sin informacion', 'sin información'):
        return 'Sin info'
    return v


def _clean_context(name):
    prefixes = ['1 Lesiones no Fatales por ', '2 Lesiones no Fatales por ',
                '3 Lesiones no Fatales contra Niños, Niñas y Adolescentes por ',
                '4 Lesiones no Fatales por ', '5 Lesiones no Fatales por ',
                '6 Lesiones no Fatales por ', '7 Lesiones no Fatales por ',
                '8 Lesiones no Fatales por ', '9 Lesiones no Fatales por ']
    for p in prefixes:
        if name.startswith(p):
            return name[len(p):]
    return name


def _agg(records, key, limit=None):
    d = {}
    for r in records:
        v = r.get(key) or 'Sin info'
        d[v] = d.get(v, 0) + 1
    items = sorted(d.items(), key=lambda x: -x[1])
    if limit:
        items = items[:limit]
    return items


def _agg_norm(records, key, limit=None):
    d = {}
    for r in records:
        v = _normalize(r.get(key) or '')
        d[v] = d.get(v, 0) + 1
    items = sorted(d.items(), key=lambda x: -x[1])
    if limit:
        items = items[:limit]
    return items


def _parse_year(val):
    if not val:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    try:
        return int(str(val).strip()[:4])
    except (ValueError, TypeError):
        return None


def dashboard(request):
    return render(request, 'dashboard.html')


def api_filters(request):
    records = get_records()
    geo_lookup = get_municipio_coords()
    dept_muns = {}
    depts_set = set()
    dept_codes = {}
    years_set = set()
    for r in records:
        resolved = resolve_record(r, geo_lookup)
        dept = resolved['dept_name']
        mun = resolved['mun_name']
        depts_set.add(dept)
        dept_codes[dept] = resolved['dept_code']
        if dept not in dept_muns:
            dept_muns[dept] = set()
        dept_muns[dept].add(mun)
        year = _parse_year(r.get(YEAR_FIELD))
        if year:
            years_set.add(year)
    return JsonResponse({
        'departamentos': sorted(depts_set),
        'dept_codes': dept_codes,
        'municipios': {d: sorted(m) for d, m in dept_muns.items()},
        'years': sorted(years_set, reverse=True),
    })


def api_report(request):
    raw_dept = request.GET.get('departamento', '').strip()
    raw_mun = request.GET.get('municipio', '').strip()
    raw_year = request.GET.get('year', '').strip()
    buffer = generate_report(departamento=raw_dept, municipio=raw_mun, year=raw_year)
    parts = [raw_dept or 'colombia', raw_mun or 'todos', raw_year or 'todos']
    filename = 'informe_lesiones_' + '_'.join(parts) + '.docx'
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def api_data(request):
    records = get_records()
    raw_dept = request.GET.get('departamento', '').strip()
    raw_mun = request.GET.get('municipio', '').strip()
    raw_year = request.GET.get('year', '').strip()
    geo_lookup = get_municipio_coords()

    filtered = []
    resolved_records = []
    for r in records:
        resolved = resolve_record(r, geo_lookup)
        if raw_dept and resolved['dept_name'] != raw_dept:
            continue
        if raw_mun and resolved['mun_name'] != raw_mun:
            continue
        if raw_year:
            year = _parse_year(r.get(YEAR_FIELD))
            if year is None or str(year) != raw_year:
                continue
        filtered.append(r)
        resolved_records.append(resolved)
    records = filtered

    total = len(records)
    by_gender = _agg_norm(records, 'identidad_de_genero')
    by_orientation = _agg_norm(records, 'orientacion_sexual')
    by_age = _agg(records, 'grupo_de_edad_de_la_victima')
    by_context_raw = _agg(records, 'contexto_de_violencia', 10)
    by_context = [(_clean_context(k), v) for k, v in by_context_raw]
    by_scenario = _agg(records, 'escenario_del_hecho', 10)
    by_month_raw = _agg(records, 'mes_del_hecho')
    by_month_raw.sort(key=lambda x: MONTH_MAP.get(x[0], 99))
    by_month = by_month_raw
    by_causal = _agg(records, 'mecanismo_causal', 10)
    by_injury = _agg(records, 'dias_de_incapacidad_medicolegal')

    year_counts = {}
    for r in records:
        y = _parse_year(r.get(YEAR_FIELD))
        if y:
            year_counts[y] = year_counts.get(y, 0) + 1
    by_year = sorted(year_counts.items())

    dept_code_agg = {}
    mun_map_data = {}
    for rec in resolved_records:
        d_code = rec['dept_code']
        if d_code not in dept_code_agg:
            dept_code_agg[d_code] = {'name': rec['dept_name'], 'count': 0}
        dept_code_agg[d_code]['count'] += 1

        m_code = rec['mun_code']
        if m_code not in mun_map_data:
            mun_map_data[m_code] = {
                'code': m_code,
                'name': rec['mun_name'],
                'count': 0,
                'lat': rec['lat'],
                'lng': rec['lng'],
            }
        mun_map_data[m_code]['count'] += 1

    map_data = [{'code': c, 'name': v['name'], 'count': v['count']}
                for c, v in sorted(dept_code_agg.items())]
    mun_map = sorted(mun_map_data.values(), key=lambda x: x['code'])

    return JsonResponse({
        'total': total,
        'by_gender': by_gender,
        'by_orientation': by_orientation,
        'by_age': by_age,
        'by_context': by_context,
        'by_scenario': by_scenario,
        'by_month': by_month,
        'by_causal': by_causal,
        'by_injury': by_injury,
        'by_year': by_year,
        'map_data': map_data,
        'mun_map': mun_map,
        'filter_dept': raw_dept,
        'filter_mun': raw_mun,
        'filter_year': raw_year,
    })
