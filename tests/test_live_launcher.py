import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import start_live

class LauncherTests(unittest.TestCase):
    def test_hidden_key_is_passed_only_through_child_environment(self):
        with patch.dict(os.environ,{},clear=True),patch('scripts.start_live.local_groq_key',return_value=None),patch('scripts.start_live.getpass.getpass',return_value='test-secret') as prompt,patch('scripts.start_live.subprocess.run') as run:
            run.return_value.returncode=0
            self.assertEqual(start_live.main(['--port','8765']),0)
            prompt.assert_called_once()
            command=run.call_args.args[0];kwargs=run.call_args.kwargs
            self.assertNotIn('test-secret',' '.join(command))
            self.assertEqual(kwargs['env']['GROQ_API_KEY'],'test-secret')
            self.assertNotIn('GROQ_API_KEY',os.environ)

    def test_existing_key_is_reused_and_evaluation_is_paced(self):
        with patch.dict(os.environ,{'GROQ_API_KEY':'existing'},clear=True),patch('scripts.start_live.local_groq_key',return_value=None),patch('scripts.start_live.getpass.getpass') as prompt,patch('scripts.start_live.subprocess.run') as run:
            run.return_value.returncode=0
            self.assertEqual(start_live.main(['--action','evaluate']),0)
            prompt.assert_not_called()
            self.assertIn('--delay-seconds',run.call_args.args[0])

    def test_first_local_key_is_used_without_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            first='gsk_'+'a'*30
            (root/'keys.local.md').write_text(first+'\n'+'gsk_'+'b'*30,encoding='utf-8')
            with patch.object(start_live,'ROOT',root),patch.dict(os.environ,{'GROQ_API_KEY':'different'},clear=True),patch('scripts.start_live.getpass.getpass') as prompt,patch('scripts.start_live.subprocess.run') as run:
                run.return_value.returncode=0
                self.assertEqual(start_live.main([]),0)
                self.assertEqual(run.call_args.kwargs['env']['GROQ_API_KEY'],first)
                prompt.assert_not_called()

if __name__=='__main__':unittest.main()
