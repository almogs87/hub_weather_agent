from io import BytesIO
import unittest
from unittest.mock import patch
from urllib.error import HTTPError,URLError
from app.schemas import Intent
from app.intent_policy import apply_metric_policy
from app.weather import WeatherClient

def intent(**changes):
    values=dict(action='weather',location_ids=['denver'],hazard='snow',start=None,end=None,threshold=0,question=None)
    values.update(changes)
    return Intent(**values)

class PlanningPolicyTests(unittest.TestCase):
    def test_wrong_heavy_snow_plan_is_corrected_and_disclosed(self):
        result,changes=apply_metric_policy('Heavy snow for denver in 2025',intent())
        self.assertEqual(result.threshold,15)
        self.assertTrue(changes)
    def test_custom_threshold_is_not_overridden(self):
        result,changes=apply_metric_policy('Heavy snow above 20 cm',intent(threshold=20))
        self.assertEqual(result.threshold,20)
        self.assertEqual(changes,[])
    def test_other_hazards_and_clarification_unchanged(self):
        self.assertEqual(apply_metric_policy('What about heat?',intent(hazard='heat',threshold=None))[0].hazard,'heat')
        self.assertEqual(apply_metric_policy('Heavy snow where?',intent(action='clarify'))[0].action,'clarify')
    def test_transient_weather_503_is_retried(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'weather'
        error=HTTPError('https://weather',503,'unavailable',{},BytesIO())
        with patch('app.weather.urlopen',side_effect=[error,Response()]) as transport,patch('app.weather.time.sleep'):
            self.assertEqual(WeatherClient.download('https://weather'),b'weather')
            self.assertEqual(transport.call_count,2)
    def test_access_denial_not_retried(self):
        denied=OSError(13,'access denied')
        with patch('app.weather.urlopen',side_effect=URLError(denied)) as transport,patch('app.weather.time.sleep') as sleep:
            with self.assertRaises(URLError):WeatherClient.download('https://weather')
            self.assertEqual(transport.call_count,1)
            sleep.assert_not_called()
    def test_weather_retries_have_a_limit(self):
        error=HTTPError('https://weather',503,'unavailable',{},BytesIO())
        with patch('app.weather.urlopen',side_effect=error) as transport,patch('app.weather.time.sleep'):
            with self.assertRaises(HTTPError):WeatherClient.download('https://weather')
            self.assertEqual(transport.call_count,3)

if __name__=='__main__':unittest.main()
