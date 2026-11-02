import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from app.providers import ModelConfig,GroqPlanner,OpenAIPlanner,build_planner

PLAN=dict(action='weather',location_ids=['denver'],hazard='snow',start='2025-01-01',end='2025-12-31',threshold=0,question=None)
class Response:
    def __init__(self,payload):self.payload=payload
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return json.dumps(self.payload).encode()

def groq_response(plan=PLAN,finish='stop'):
    return Response(dict(choices=[dict(finish_reason=finish,message=dict(content=json.dumps(plan)))]))

class ProviderTests(unittest.TestCase):
    def test_groq_default_and_switch_without_code_change(self):
        with patch.dict(os.environ,{},clear=True):
            config=ModelConfig.load()
            self.assertEqual(config.provider,'groq')
            self.assertEqual(config.model,'openai/gpt-oss-20b')
            self.assertIsInstance(build_planner(),GroqPlanner)
        with patch.dict(os.environ,{'LLM_PROVIDER':'groq','LLM_MODEL':'openai/gpt-oss-120b'},clear=True):
            self.assertEqual(build_planner().config.model,'openai/gpt-oss-120b')
        with patch.dict(os.environ,{'LLM_PROVIDER':'openai','LLM_MODEL':'test-model'},clear=True):
            self.assertIsInstance(build_planner(),OpenAIPlanner)
        with patch.dict(os.environ,{'LLM_PROVIDER':'unknown'},clear=True):
            with self.assertRaises(ValueError):build_planner()

    def test_strict_schema_and_shared_intent(self):
        with patch.dict(os.environ,{'GROQ_API_KEY':'fake-test-key'},clear=True),patch('app.providers.urlopen',return_value=groq_response()) as mock:
            result=GroqPlanner()('snow',{}, {})
            request=mock.call_args.args[0]
            body=json.loads(request.data)
            self.assertEqual(request.full_url,'https://api.groq.com/openai/v1/chat/completions')
            self.assertTrue(body['response_format']['json_schema']['strict'])
            self.assertNotIn('tools',body)
            self.assertEqual(result.start.year,2025)
            self.assertNotIn('fake-test-key',json.dumps(ModelConfig.load().public()))

    def test_invalid_or_truncated_plan_never_accepted(self):
        invalid=dict(PLAN,arbitrary_code='not allowed')
        for response in [groq_response(invalid),groq_response(finish='length'),Response(dict(choices=[]))]:
            with patch.dict(os.environ,{'GROQ_API_KEY':'test'},clear=True),patch('app.providers.urlopen',return_value=response):
                with self.assertRaises(ValueError):GroqPlanner()('snow',{}, {})

    def test_missing_key_and_rate_limit_do_not_fallback(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(RuntimeError,'GROQ_API_KEY'):GroqPlanner()('snow',{}, {})
        error=HTTPError('https://api.groq.com',429,'limited',{},None)
        with patch.dict(os.environ,{'GROQ_API_KEY':'test'},clear=True),patch('app.providers.urlopen',side_effect=error) as mock:
            with self.assertRaisesRegex(RuntimeError,'quota'):GroqPlanner()('snow',{}, {})
            self.assertEqual(mock.call_count,1)

if __name__=='__main__':unittest.main()
