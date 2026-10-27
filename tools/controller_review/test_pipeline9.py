"""Hostile result archives must be rejected before they can execute anything."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[2]

class ImportContracts(unittest.TestCase):
    def reject(self,name,attrs=None):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'bad.zip';run=root/'run';run.mkdir()
            with zipfile.ZipFile(archive,'w') as z:
                entry=zipfile.ZipInfo(name)
                if attrs is not None:entry.external_attr=attrs
                z.writestr(entry,'untrusted')
            proc=subprocess.run([sys.executable,str(ROOT/'tools/controller_review/import_laptop9.py'),'--run',str(run),'--results',str(archive)],capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0);self.assertIn('AssertionError',proc.stderr)
            self.assertFalse((run/'target-laptop'/name).exists())
    def test_parent_traversal(self):self.reject('../escape.json')
    def test_absolute_path(self):self.reject('/tmp/lans-no-write.json')
    def test_windows_traversal(self):self.reject('..\\escape.json')
    def test_executable_input(self):self.reject('run.py')
    def test_symlink(self):self.reject('alias.json',0o120777<<16)

if __name__=='__main__':unittest.main()
