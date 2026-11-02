"""Illustrative city hubs, not actual company facilities."""
EXAMPLE_HUBS = [
    dict(id='chicago', latitude=41.8781, longitude=-87.6298, timezone='America/Chicago', state='IL', region='Midwest', county_fips='17031'),
    dict(id='detroit', latitude=42.3314, longitude=-83.0458, timezone='America/Detroit', state='MI', region='Midwest', county_fips='26163'),
    dict(id='minneapolis', latitude=44.9778, longitude=-93.2650, timezone='America/Chicago', state='MN', region='Midwest', county_fips='27053'),
    dict(id='miami', latitude=25.7617, longitude=-80.1918, timezone='America/New_York', state='FL', region='South', county_fips='12086'),
    dict(id='houston', latitude=29.7604, longitude=-95.3698, timezone='America/Chicago', state='TX', region='South', county_fips='48201'),
    dict(id='denver', latitude=39.7392, longitude=-104.9903, timezone='America/Denver', state='CO', region='West', county_fips='08031'),
    dict(id='dallas', latitude=32.7767, longitude=-96.7970, timezone='America/Chicago', state='TX', region='South', county_fips='48113'),
]

def seed_examples(store):
    """Preserve user locations, enriching exact matches or adding a distinct example."""
    with store.connect() as db:
        import json
        for hub in EXAMPLE_HUBS:
            row = db.execute('SELECT payload FROM locations WHERE id=?', (hub['id'],)).fetchone()
            if not row:
                db.execute('INSERT INTO locations VALUES (?,?)', (hub['id'], json.dumps(dict(hub, example=True))))
                continue
            existing = json.loads(row[0])
            if all(existing.get(k) == hub[k] for k in ('latitude', 'longitude', 'timezone')):
                for field in ('state', 'region', 'county_fips'):
                    existing.setdefault(field, hub[field])
                db.execute('UPDATE locations SET payload=? WHERE id=?', (json.dumps(existing), hub['id']))
            elif not existing.get('example'):
                example = dict(hub, id='example_'+hub['id'], example=True)
                db.execute('INSERT OR IGNORE INTO locations VALUES (?,?)', (example['id'], json.dumps(example)))
