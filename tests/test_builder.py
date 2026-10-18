"""Offline safety and packaging tests; do not download Bitwarden or access vault data."""
from pathlib import Path
from tempfile import TemporaryDirectory
import configparser
import importlib.util
import unittest

ROOT = Path(__file__).parents[1]

def module(name):
    path = ROOT / 'builder' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

b = module('build_portable')
z = module('verify_zip')


def fake_release(version='2026.10.0', digest=True):
    return {
        'tag_name': 'desktop-v' + version,
        'draft': False, 'prerelease': False,
        'assets': [
            {'name': 'Bitwarden-Portable-' + version + '.exe', 'state': 'uploaded',
             'browser_download_url': 'https://github.com/bitwarden/clients/releases/download/desktop-v' + version + '/Bitwarden-Portable-' + version + '.exe',
             'digest': 'sha256:' + b.PINNED_CHECKSUMS['2026.10.0'] if digest else None},
            {'name': 'commercial-Bitwarden-Portable-' + version + '.exe', 'state': 'uploaded'}
        ]
    }

class Tests(unittest.TestCase):
    def test_official_release_hash(self):
        url, checksum = b.validate_release(fake_release(), '2026.10.0')
        self.assertTrue(url.endswith('Bitwarden-Portable-2026.10.0.exe'))
        self.assertEqual(checksum, b.PINNED_CHECKSUMS['2026.10.0'])

    def test_reject_beta_release(self):
        info=fake_release()
        info['prerelease']=True
        with self.assertRaisesRegex(ValueError,'stable'):
            b.validate_release(info,'2026.10.0')

    def test_reject_malicious_version(self):
        with self.assertRaises(ValueError):
            b.validate_release(fake_release(), '../latest')

    def test_reject_unverified_hash(self):
        rel=fake_release('2026.11.0',digest=False)
        with self.assertRaisesRegex(ValueError,'digest unavailable'):
            b.validate_release(rel,'2026.11.0')

    def test_future_release_can_use_user_checksum_when_digest_missing(self):
        rel=fake_release('2026.11.0',digest=False)
        self.assertEqual(b.validate_release(rel,'2026.11.0','a'*64)[1],'a'*64)

    def test_reject_checksum_disagreement(self):
        with self.assertRaisesRegex(ValueError,'disagree'):
            b.validate_release(fake_release(),'2026.10.0','f'*64)

    def test_reject_wrong_source_url(self):
        rel=fake_release()
        rel['assets'][0]['browser_download_url']='https://evil.example/download.exe'
        with self.assertRaisesRegex(ValueError,'Official'):
            b.validate_release(rel,'2026.10.0')

    def test_launcher_sets_portable_data_without_overriding_user_profile(self):
        code=(ROOT/'builder'/'BitwardenPortable.cs').read_text()
        self.assertIn('BITWARDEN_APPDATA_DIR',code)
        self.assertIn('Data\\Bitwarden',code)
        self.assertNotIn('EnvironmentVariables["APPDATA"]',code)
        self.assertNotIn('EnvironmentVariables["USERPROFILE"]',code)

    def test_icon_conversion_uses_original_ico(self):
        from PIL import Image
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)
            icon=folder/'icon.ico'
            Image.new('RGBA',(256,256), (0,90,160,255)).save(icon, format='ICO', sizes=[(16,16),(32,32),(48,48),(128,128),(256,256)])
            b.render_icons(icon,folder)
            for sz in (16,32,75,128,256):
                self.assertTrue((folder/f'appicon_{sz}.png').exists())

    def test_zip_package_rejects_sensitive_data(self):
        with TemporaryDirectory() as tmp:
            stage=Path(tmp)/'BitwardenPortable'
            files=['BitwardenPortable.exe','App/Bitwarden/Bitwarden-Portable.exe','App/AppInfo/appinfo.ini','App/AppInfo/appicon.ico','Data/README-PRESERVE-DURING-UPDATE.txt','Other/Source/BUILD-INFO.txt','Other/Source/SECURITY.txt']+[f'App/AppInfo/appicon_{n}.png' for n in (16,32,75,128,256)]
            for name in files:
                p=stage/name;p.parent.mkdir(parents=True,exist_ok=True)
                if name.endswith('.exe'):
                    with p.open('wb') as f:
                        f.write(b'MZ'); f.truncate(10_000_001)
                elif name.endswith('appinfo.ini'):
                    p.write_text('[Format]\nVersion=3.9\n[Details]\nName=Bitwarden Portable (Community)\nCategory=Security\n[Control]\nStart=BitwardenPortable.exe\n')
                else: p.write_text('test')
            z.validate(stage)
            (stage/'Data'/'Bitwarden').mkdir()
            (stage/'Data'/'Bitwarden'/'encrypted-vault.json').write_text('secret')
            with self.assertRaisesRegex(AssertionError,'vault data'):
                z.validate(stage)

    def test_build_stage_from_verified_mocked_release(self):
        from unittest.mock import patch
        from PIL import Image
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            stage=root/'BitwardenPortable'
            cache=root/'cache'
            def fake_download(url, target, max_size):
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.suffix == '.ico':
                    Image.new('RGBA',(256,256),(30,60,125,255)).save(target,format='ICO')
                else:
                    with target.open('wb') as writer:
                        writer.write(b'MZ')
                        writer.truncate(11_000_000)
            with patch.object(b,'get_json',return_value=fake_release()), patch.object(b,'download',side_effect=fake_download), patch.object(b,'sha256_file',return_value=b.PINNED_CHECKSUMS['2026.10.0']):
                b.build('2026.10.0',stage,cache)
            self.assertTrue((stage/'App/Bitwarden/Bitwarden-Portable.exe').exists())
            self.assertTrue((stage/'App/AppInfo/appicon.ico').exists())
            self.assertFalse((stage/'Data/Bitwarden').exists())
            self.assertEqual((stage/'App/AppInfo/appinfo.ini').read_text().count('Category=Security'),1)

    def test_manual_only_workflow_and_clean_gitignore(self):
        yml=(ROOT/'.github/workflows/build-bitwarden-portable.yml').read_text()
        self.assertIn('workflow_dispatch:',yml)
        self.assertNotIn('\n  schedule:',yml)
        self.assertIn('retention-days: 7',yml)
        ignore=(ROOT/'.gitignore').read_text()
        self.assertIn('**/Data/',ignore)

if __name__=='__main__':unittest.main()
