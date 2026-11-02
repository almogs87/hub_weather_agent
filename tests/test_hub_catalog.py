import json
from pathlib import Path
import tempfile
import unittest
from app.hubs import load_hubs
from app.storage import Store

class HubCatalogTests(unittest.TestCase):
    def test_catalog_is_active_without_changing_saved_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.db'
            saved=Store(path)
            saved.add_location(dict(id='private',latitude=1,longitude=2,timezone='UTC'))
            active=Store(path,catalog=load_hubs())
            self.assertIn('chicago',active.locations())
            self.assertNotIn('private',active.locations())
            self.assertIn('private',saved.locations())

    def test_duplicate_and_invalid_catalog_rejected(self):
        hub=next(iter(load_hubs().values()))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'hubs.json'
            path.write_text(json.dumps([hub,hub]),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Duplicate'):load_hubs(path)
            path.write_text(json.dumps([dict(hub,county_fips='bad')]),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'county FIPS'):load_hubs(path)

if __name__=='__main__':unittest.main()
