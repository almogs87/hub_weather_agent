import json
import tempfile
import unittest
from app.fema import FEMAClient
from app.hubs import seed_examples
from app.storage import Store

class FEMAClientTests(unittest.TestCase):
    def test_cache_and_missing_score(self):
        attrs = dict(STCOFIPS='48201', COUNTY='Harris', STATEABBRV='TX', NRI_VER='1.20', HRCN_EALS=85, IFLD_EALS=70, CFLD_EALS=None, WNTW_EALS=10)
        raw = json.dumps({'features': [{'attributes': attrs}]}).encode()
        with tempfile.TemporaryDirectory() as directory:
            client = FEMAClient(directory, lambda url: raw)
            first = client.fetch('48201')
            second = client.fetch('48201')
            self.assertIsNone(first['scores']['coastal_flood'])
            self.assertEqual(first['scores']['hurricane'], 85)
            self.assertFalse(first['evidence']['cache_hit'])
            self.assertTrue(second['evidence']['cache_hit'])
            with self.assertRaises(ValueError): client.fetch('48201x')

    def test_seeding_does_not_replace_user_location(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory + '/test.sqlite')
            store.add_location(dict(id='denver', latitude=1, longitude=2, timezone='UTC'))
            seed_examples(store)
            seed_examples(store)
            self.assertEqual(len(store.locations()), 8)
            self.assertEqual(store.locations()['denver']['latitude'], 1)
            self.assertTrue(store.locations()['example_denver']['example'])

    def test_existing_matching_city_receives_county_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory + '/test.sqlite')
            store.add_location(dict(id='chicago', latitude=41.8781, longitude=-87.6298, timezone='America/Chicago'))
            seed_examples(store)
            self.assertEqual(store.locations()['chicago']['county_fips'], '17031')
            self.assertEqual(len(store.locations()), 7)

if __name__ == '__main__': unittest.main()
