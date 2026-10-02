"""Company identity, lossless intelligence merge, and deterministic derived views."""
from __future__ import annotations

from copy import deepcopy
import math
import re
from statistics import median
import unicodedata
import uuid

VALUES = ('Research', 'Access', 'Execution', 'Financing', 'Performance', 'Risk',
          'Distribution', 'Technology', 'Service', 'Trust')
SECTIONS = ('control', 'operate', 'source')
TYPES = {
    'control': ('Controlling shareholder', 'Largest shareholder', 'Dominant shareholder',
                'Founder', 'Chairman', 'CEO', 'CIO', 'General manager', 'Business head'),
    'operate': ('Parent', 'Subsidiary', 'Branch'),
    'source': ('Supplier',),
}


def normalize(value):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', str(value or '')).casefold()))


def resolve(companies, company_id=None, name=''):
    if company_id:
        found = next((c for c in companies if c.get('id') == company_id), None)
        if found is not None:
            return found
    name = normalize(name)
    if not name:
        return None
    for c in companies:
        if name in [normalize(a) for a in c.get('aliases', [])]:
            return c
    return next((c for c in companies if normalize(c.get('name')) == name), None)


def merge_data(old, new):
    """Incoming explicit scalars win; omitted keys and distinct list entries survive."""
    result = deepcopy(old)
    for key, value in new.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_data(result[key], value)
        elif isinstance(value, list) and isinstance(result.get(key), list):
            for item in value:
                if item not in result[key]:
                    result[key].append(deepcopy(item))
        else:
            result[key] = deepcopy(value)
    return result


def merge_rows(old, new, key, merge=merge_data):
    result = deepcopy(old)
    for row in new:
        index = next((i for i, r in enumerate(result) if key(r) == key(row)), None)
        if index is None:
            result.append(deepcopy(row))
        else:
            result[index] = merge(result[index], row)
    return result


def merge_client(old, new):
    result = merge_data(old, {k: v for k, v in new.items() if k != 'observations'})
    result['observations'] = merge_rows(old.get('observations', []), new.get('observations', []),
                                        lambda o: str(o.get('period')))
    return result


def merge_companies(old, incoming):
    result = deepcopy(old)
    for item in incoming:
        found = resolve(result, item.get('id'), item.get('name'))
        if found is None:
            for alias in item.get('aliases', []):
                found = resolve(result, name=alias)
                if found is not None:
                    break
        if found is None:
            found = {'id': item.get('id') or uuid.uuid5(uuid.NAMESPACE_URL, 'company:' + normalize(item['name'])).hex, 'name': item['name'],
                     'aliases': [], 'clients': [], 'delivery': []}
            result.append(found)
        merged = merge_data(found, {k: v for k, v in item.items() if k not in ('clients', 'delivery', 'id')})
        if normalize(found['name']) != normalize(merged['name']):
            merged['aliases'] = list(dict.fromkeys([*merged.get('aliases', []), found['name']]))
        merged['clients'] = merge_rows(found.get('clients', []), item.get('clients', []),
            lambda r: (normalize(r.get('client')), normalize(r.get('service'))), merge_client)
        merged['delivery'] = merge_rows(found.get('delivery', []), item.get('delivery', []),
            lambda r: (r.get('section'), normalize(r.get('entity')), normalize(r.get('type'))))
        result[result.index(found)] = merged
    return result


def company_union(companies, jobs):
    result = merge_companies([], companies)
    for job in jobs:
        if resolve(result, job.company_id, job.company) is None:
            result.append({'id': job.company_id or uuid.uuid5(uuid.NAMESPACE_URL, 'company:' + normalize(job.company)).hex,
                           'name': job.company, 'aliases': [], 'clients': [], 'delivery': []})
    return sorted(result, key=lambda c: (normalize(c['name']), c['id']))


def validate_companies(companies):
    if not isinstance(companies, list):
        raise ValueError('companies must be an array.')
    for c in companies:
        if not isinstance(c, dict) or not isinstance(c.get('name'), str) or not c['name'].strip():
            raise ValueError('Company name is required.')
        if c.get('id') is not None and not isinstance(c['id'], str):
            raise ValueError('Company id must be a string.')
        if not isinstance(c.get('aliases', []), list) or any(not isinstance(a, str) for a in c.get('aliases', [])):
            raise ValueError('aliases must be strings.')
        for key in ('clients', 'delivery'):
            if not isinstance(c.get(key, []), list) or any(not isinstance(r, dict) for r in c.get(key, [])):
                raise ValueError(f'{key} must be an array of objects.')
        for row in c.get('delivery', []):
            if row.get('section') not in SECTIONS:
                raise ValueError('Delivery section must be control, operate, or source.')
            for key in ('entity', 'type'):
                if not isinstance(row.get(key), str) or not row[key].strip():
                    raise ValueError(f'Delivery {key} is required.')
        for row in c.get('clients', []):
            for key in ('client', 'service'):
                if not isinstance(row.get(key), str) or not row[key].strip():
                    raise ValueError(f'Client {key} is required.')
            if not isinstance(row.get('observations', []), list) or any(not isinstance(o, dict) for o in row.get('observations', [])):
                raise ValueError('observations must be an array of objects.')


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def latest(row):
    return max(row.get('observations', []), key=lambda o: period_key(o.get('period')), default={})


def period_key(period):
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.findall(r'\d+|\D+', str(period or '')))


def signature(observation, kind, row):
    amount = observation.get(kind) or {}
    if not isinstance(amount, dict) or not amount.get('currency'):
        return None
    if amount.get('period', observation.get('period')) != observation.get('period'):
        return None
    if normalize(amount.get('service', observation.get('service', row.get('service')))) != normalize(row.get('service')):
        return None
    return (amount['currency'], amount.get('unit', amount.get('units', 'currency')), normalize(row.get('service')))


def share(row, observation=None):
    observation = latest(row) if observation is None else observation
    w, c = observation.get('wallet') or {}, observation.get('capture') or {}
    if not isinstance(w, dict) or not isinstance(c, dict):
        return None
    wa, ca = w.get('amount'), c.get('amount')
    if (not observation.get('period') or not normalize(row.get('service')) or
        not number(wa) or not number(ca) or wa <= 0 or ca < 0):
        return None
    sig = signature(observation, 'wallet', row)
    if sig is None or sig != signature(observation, 'capture', row):
        return None
    return ca / wa


def momentum(row):
    observations = sorted(row.get('observations', []), key=lambda o: period_key(o.get('period')), reverse=True)
    if observations:
        current = observations[0]
        value = share(row, current)
        for previous in observations[1:]:
            old = share(row, previous)
            if (value is not None and old is not None and previous.get('period') != current.get('period')
                and signature(current, 'wallet', row) == signature(previous, 'wallet', row)
                and re.sub(r'\d', '#', str(current['period'])) == re.sub(r'\d', '#', str(previous['period']))):
                return (value - old) * 100
    return row.get('momentum') if row.get('momentum') in ('up', 'flat', 'down') else None


def display_delta(value):
    return f'{value:+.1f}pp' if number(value) else {'up': '↑', 'flat': '→', 'down': '↓'}.get(value, '-')


def display_share(value):
    return '-' if value is None else f'{value * 100:.1f}%'


def money(amount):
    if not isinstance(amount, dict) or not number(amount.get('amount')):
        return '-'
    value = amount['amount']
    scale, suffix = next(((n, s) for n, s in ((1e9, 'bn'), (1e6, 'm'), (1e3, 'k')) if abs(value) >= n), (1, ''))
    currency = amount.get('currency')
    if not currency:
        return '-'
    prefix = {'CNY': '¥', 'USD': '$', 'EUR': '€', 'GBP': '£'}.get(currency, currency + ' ')
    unit = amount.get('unit', amount.get('units', 'currency'))
    return f'{prefix}{value / scale:g}{suffix}' + (f' {unit}' if unit != 'currency' else '')


def capture_weights(rows):
    signatures, weights = [], []
    for row in rows:
        o = latest(row)
        capture = o.get('capture') or {}
        sig = signature(o, 'capture', row)
        if sig is None or not o.get('period') or not number(capture.get('amount')) or capture['amount'] < 0:
            return None
        signatures.append((sig, o['period']))
        weights.append(capture['amount'])
    if not signatures or len(set(signatures)) != 1 or sum(weights) <= 0:
        return None
    return weights


def aggregate(company):
    rows = company.get('clients', [])
    weights = capture_weights(rows)
    segments = {}
    for i, row in enumerate(rows):
        segment = row.get('segment') or '-'
        if weights is not None:
            segments[segment] = segments.get(segment, 0) + weights[i]
        else:
            segments.setdefault(segment, set()).add(normalize(row.get('client')))
    if weights is None:
        segments = {k: len(v) for k, v in segments.items()}
    leading, cumulative = [], 0
    for name, weight in sorted(segments.items(), key=lambda kv: (-kv[1], kv[0].casefold())):
        # Residual Other / unknown buckets carry weight but do not identify a
        # leading client segment (e.g. 30% Public + 22% Hedge + 28% Other).
        if normalize(name) in ('other', ''):
            continue
        leading.append(name)
        cumulative += weight
        if cumulative > sum(segments.values()) / 2:
            break
    shares = [s for row in rows if (s := share(row)) is not None]
    deltas = [momentum(row) for row in rows]
    numeric = [d for d in deltas if number(d)]
    qualitative = [d for d in deltas if isinstance(d, str)]
    delta = median(numeric) if numeric else next((d for d in ('up', 'flat', 'down') if qualitative.count(d) > len(qualitative) / 2), None)
    valued = [r for r in rows if r.get('value') in VALUES]
    value_weights = capture_weights(valued)
    tags = {}
    for i, row in enumerate(valued):
        tags[row['value']] = tags.get(row['value'], 0) + (value_weights[i] if value_weights is not None else 1)
    return (str(len({normalize(r.get('client')) for r in rows if normalize(r.get('client'))})),
            ' · '.join(leading) or '-', display_share(median(shares) if shares else None),
            display_delta(delta), sorted(tags, key=lambda t: (-tags[t], t))[0] if tags else '-')


def relevance(job, client):
    def terms(value):
        return {normalize(v) for v in (value if isinstance(value, list) else [value]) if normalize(v)}
    data = job.to_dict()
    result = []
    for job_key, client_key in (('service', 'service'), ('coverage', 'coverage'), ('geography', 'geography'), ('client_segment', 'segment'), ('value', 'value')):
        a, b = terms(data.get(job_key)), terms(client.get(client_key))
        if job_key == 'value':
            a &= {normalize(v) for v in VALUES}
            b &= {normalize(v) for v in VALUES}
        result.append(len(a & b))
    text = normalize(' '.join(str(data.get(k) or '') for k in ('job', 'role', 'program', 'description_text', 'brief', 'description')))
    context = normalize(' '.join(str(client.get(k) or '') for k in ('client', 'service', 'coverage', 'geography', 'segment', 'value')))
    result.append(len(set(text.split()) & set(context.split())))
    return tuple(-v for v in result)
