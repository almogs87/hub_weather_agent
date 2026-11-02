import os
import unittest
from unittest.mock import patch
from scripts import start_live

class LauncherTests(unittest.TestCase):
    def test_hidden_key_is_passed_only_through_child_environment(self):
        with patch.dict(os.environ,{},clear=True),patch('scripts.start_live.getpass.getpass',return_value='test-secret') as prompt,patch('scripts.start_live.subprocess.run') as run:
            run.return_value.returncode=0
            self.assertEqual(start_live.main(['--port','8765']),0)
            prompt.assert_called_once()
            command=run.call_args.args[0];kwargs=run.call_args.kwargs
            self.assertNotIn('test-secret',' '.join(command))
            self.assertEqual(kwargs['env']['GROQ_API_KEY'],'test-secret')
            self.assertNotIn('GROQ_API_KEY',os.environ)

    def test_existing_key_is_reused_and_evaluation_is_paced(self):
        with patch.dict(os.environ,{'GROQ_API_KEY':'existing'},clear=True),patch('scripts.start_live.getpass.getpass') as prompt,patch('scripts.start_live.subprocess.run') as run:
            run.return_value.returncode=0
            self.assertEqual(start_live.main(['--action','evaluate']),0)
            prompt.assert_not_called()
            self.assertIn('--delay-seconds',run.call_args.args[0])

if __name__=='__main__':unittest.main()
