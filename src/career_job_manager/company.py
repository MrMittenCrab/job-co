"""Company identity and the six canonical company tables."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
import unicodedata
import uuid

TABLES = {
    'strategy': ('Department', 'Revenue', 'Rank', 'Model'),
    'makeup': ('Department', 'Revenue', 'Scale', 'Mix'),
    'direction': ('Department', 'Revenue', 'Growth', 'Edge'),
    'clients': ('Client', 'Period', 'Engagement', 'Role'),
    'franchise': ('Entity', 'Parent', 'Footprint'),
    'leadership': ('Layer', 'Parent', 'Composition'),
}
TABLE_KEYS = dict(zip('smdcfl', TABLES))
SEPARATOR = ' · '
MISSING = {'', '-', 'undisclosed', 'n/d', 'n/a', 'unknown', 'not disclosed'}
LEGACY_CLIENT_FIELDS = {'service', 'segment', 'observations', 'wallet', 'capture',
                        'share', 'momentum', 'value', 'benefit', 'coverage', 'geography'}


def cell(value):
    """Only literal middle dots define phrases; missing phrases carry no facts."""
    phrases = [part.strip() for part in str(value if value is not None else '').split('·')]
    return SEPARATOR.join(p for p in phrases if p.casefold() not in MISSING) or '-'


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


def migrate_company(company, *, fill=True):
    """Discard obsolete intelligence, retaining identity and unrelated metadata."""
    result = deepcopy(company)
    if 'profile_edited' not in result:
        # Recover profile/identity work before obsolete intelligence is discarded.
        # Empty tables and dates alone say nothing about historical edits.
        def substantive(value):
            if isinstance(value, dict):
                return any(substantive(v) for k, v in value.items() if k != 'id')
            if isinstance(value, list):
                return any(substantive(v) for v in value)
            return value is not None and cell(value) != '-'
        result['profile_edited'] = any(substantive(result.get(key)) for key in (
            *TABLES, 'composition', 'value', 'delivery', 'aliases', 'evidence',
            'research_profile', 'research_notes', 'ownership_bucket'))
    if 'composition' in result:
        result.setdefault('makeup', []).extend(result.pop('composition'))
    for row in result.get('strategy', []):
        if 'position' in row:
            legacy = cell(row.pop('position'))
            rank = cell(row.get('rank'))
            # Preserve distinct values if a partially migrated row has both keys.
            row['rank'] = cell(SEPARATOR.join(dict.fromkeys(
                value for value in (rank, legacy) if value != '-')))
    result.pop('value', None)
    result.pop('delivery', None)
    # Old VALUE relationships share a storage name with the new CLIENTS table.
    # Their fields identify them; never convert any of their contents.
    result['clients'] = [r for r in result.get('clients', [])
                         if not LEGACY_CLIENT_FIELDS.intersection(r)]
    for table, columns in TABLES.items():
        result.setdefault(table, [])
        for row in result[table]:
            for column in columns:
                key = column.lower()
                if fill or key in row:
                    row[key] = cell(row.get(key))
    return result


def merge_companies(old, incoming):
    result = [migrate_company(c) for c in old]
    for item in incoming:
        item = migrate_company(item, fill=False)
        found = resolve(result, item.get('id'), item.get('name'))
        if found is None:
            for alias in item.get('aliases', []):
                found = resolve(result, name=alias)
                if found is not None:
                    break
        if found is None:
            found = {'id': item.get('id') or uuid.uuid5(uuid.NAMESPACE_URL, 'company:' + normalize(item['name'])).hex,
                     'name': item['name'], 'aliases': []}
            found.update(deepcopy(item))
            result.append(migrate_company(found))
            continue
        merged = merge_data(found, {k: v for k, v in item.items() if k not in (*TABLES, 'id')})
        merged['profile_edited'] = found['profile_edited'] or item['profile_edited']
        if normalize(found['name']) != normalize(merged['name']):
            merged['aliases'] = list(dict.fromkeys([*merged.get('aliases', []), found['name']]))
        for table, columns in TABLES.items():
            rows = deepcopy(found.get(table, []))
            def identity(row):
                if row.get('id'):
                    return ('id', row['id'])
                return (normalize(row.get(columns[0].lower())),
                        cell(row.get('period')) if table == 'clients' else '')
            for row in item[table]:
                index = next((i for i, r in enumerate(rows) if identity(r) == identity(row)), None)
                if index is None:
                    rows.append(deepcopy(row))
                else:
                    rows[index] = merge_data(rows[index], row)
            merged[table] = rows
        result[result.index(found)] = merged
    return result


def company_union(companies, jobs):
    result = merge_companies([], companies)
    for job in jobs:
        if resolve(result, job.company_id, job.company) is None:
            result.append(migrate_company({
                'id': job.company_id or uuid.uuid5(uuid.NAMESPACE_URL, 'company:' + normalize(job.company)).hex,
                'name': job.company, 'aliases': []}))
    return sorted(result, key=company_home_key)


def company_home_key(company):
    return (not company['profile_edited'], normalize(company['name']), company['id'])


def validate_companies(companies):
    if not isinstance(companies, list):
        raise ValueError('companies must be an array.')
    for company in companies:
        if not isinstance(company, dict) or not isinstance(company.get('name'), str) or not company['name'].strip():
            raise ValueError('Company name is required.')
        if company.get('id') is not None and not isinstance(company['id'], str):
            raise ValueError('Company id must be a string.')
        if 'profile_edited' in company and type(company['profile_edited']) is not bool:
            raise ValueError('profile_edited must be a boolean.')
        if not isinstance(company.get('aliases', []), list) or any(not isinstance(a, str) for a in company.get('aliases', [])):
            raise ValueError('aliases must be strings.')
        for table, columns in {**TABLES, 'composition': TABLES['makeup']}.items():
            rows = company.get(table, [])
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise ValueError(f'{table} must be an array of objects.')
            for row in rows:
                if table == 'clients' and LEGACY_CLIENT_FIELDS.intersection(row):
                    continue  # Obsolete imports are discarded, just like stored data.
                for column in columns:
                    value = row.get(column.lower())
                    if value is not None and not isinstance(value, str):
                        raise ValueError(f'{column} must be text or null.')


def revenue_key(value):
    text = cell(value).casefold().replace(',', '')
    match = re.fullmatch(
        r'\s*(?:(?:(?:usd|hkd|cny|rmb|eur|gbp|jpy|chf|aud|cad|sgd|nzd|inr|krw|'
        r'twd|sek|nok|dkk|aed|sar|zar|brl|mxn)\s*[$€£¥￥₹₩]?|'
        r'(?:us|hk|a|c|s|nz|nt)\$|[$€£¥￥₹₩])\s*)?'
        r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(k|mn|m|bn|b|tn|t)?\s*', text)
    if not match:
        return (True, Decimal(0))
    try:
        amount = Decimal(match[1]) * {'k': 10**3, 'mn': 10**6, 'm': 10**6,
                                    'bn': 10**9, 'b': 10**9, 'tn': 10**12, 't': 10**12, None: 1}[match[2]]
        return (False, -amount)
    except InvalidOperation:
        return (True, Decimal(0))


def period_key(value):
    years = re.findall(r'(?<!\d)\d{4}(?!\d)', cell(value))
    return (not bool(years), -int(years[-1]) if years else 0)


def ordered_rows(company, table):
    rows = list(company.get(table, []))
    if table in ('strategy', 'makeup', 'direction'):
        rows.sort(key=lambda r: revenue_key(r.get('revenue')))
    elif table == 'clients':
        rows.sort(key=lambda r: period_key(r.get('period')))
    return rows


def departments(company):
    return cell(SEPARATOR.join(cell(r.get('department')) for r in ordered_rows(company, 'strategy')))
