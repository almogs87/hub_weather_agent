"""County-level FEMA National Risk Index evidence, cached with provenance."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

SERVICE = 'https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0/query'
FIELDS = {'hurricane': 'HRCN_EALS', 'inland_flood': 'IFLD_EALS', 'coastal_flood': 'CFLD_EALS', 'winter': 'WNTW_EALS', 'ice_storm': 'ISTM_EALS', 'tornado': 'TRND_EALS', 'drought': 'DRGT_EALS'}

class FEMAClient:
    def __init__(self, cache_dir='data/cache/fema', transport=None):
        self.cache_dir = Path(cache_dir)
        self.transport = transport or self.download

    @staticmethod
    def download(url):
        with urlopen(url, timeout=30) as response:
            return response.read()

    def fetch(self, county_fips, refresh=False):
        if not isinstance(county_fips, str) or len(county_fips) != 5 or not county_fips.isascii() or not county_fips.isdigit():
            raise ValueError('County FIPS must be five digits')
        url = SERVICE + '?' + urlencode({'where': "STCOFIPS='" + county_fips + "'", 'outFields': ','.join(['STCOFIPS', 'COUNTY', 'STATEABBRV', 'NRI_VER', *FIELDS.values()]), 'returnGeometry': 'false', 'f': 'json'})
        path = self.cache_dir / (county_fips + '-' + sha256(url.encode()).hexdigest()[:16] + '.json')
        if path.exists() and not refresh:
            envelope = json.loads(path.read_text(encoding='utf-8'))
            if envelope['url'] != url or sha256(envelope['raw'].encode('utf-8')).hexdigest() != envelope['sha256']:
                raise ValueError('FEMA cache integrity failure')
            cached = True
        else:
            try:
                raw = self.transport(url).decode('utf-8')
            except Exception as exc:
                raise RuntimeError('FEMA county data download failed') from exc
            envelope = dict(url=url, raw=raw, sha256=sha256(raw.encode('utf-8')).hexdigest(), retrieved_at=datetime.now(timezone.utc).isoformat())
            cached = False
        payload = json.loads(envelope['raw'])
        features = payload.get('features', [])
        if payload.get('error') or len(features) != 1:
            raise ValueError('FEMA response must contain exactly one county')
        attrs = features[0]['attributes']
        if attrs.get('STCOFIPS') != county_fips or not attrs.get('NRI_VER'):
            raise ValueError('FEMA county identity or version missing')
        scores = {}
        for hazard, field in FIELDS.items():
            value = attrs.get(field)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100):
                raise ValueError('Invalid FEMA score: ' + field)
            scores[hazard] = value
        if not cached:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(envelope), encoding='utf-8')
        return dict(county_fips=county_fips, county=attrs.get('COUNTY'), state=attrs.get('STATEABBRV'), scores=scores,
                    evidence=dict(source='FEMA National Risk Index', version=attrs['NRI_VER'], url=url, sha256=envelope['sha256'], retrieved_at=envelope['retrieved_at'], cache_hit=cached,
                                  limitation='County-level expected annual loss scores are relative community measures, not facility-specific disruption probabilities.'))
