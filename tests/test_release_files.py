import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import release


ROOT = Path(__file__).resolve().parents[1]


class ReleaseFileTests(unittest.TestCase):
    def test_server_configuration_mappings(self):
        self.assertEqual(release.RELEASE_ROOT_FILE_MAPPINGS[os.path.join('backend', '.htaccess')], '.htaccess')
        self.assertEqual(release.RELEASE_ROOT_FILE_MAPPINGS[os.path.join('backend', '.user.ini')], '.user.ini')

    def test_root_configuration_is_copied_and_php_settings_remain_unchanged(self):
        sources = {ROOT / source: name for source, name in release.RELEASE_ROOT_FILE_MAPPINGS.items()}
        original = {source: source.read_bytes() for source in sources}
        # Isolate copying from the real release directory and avoid copying assets.
        with tempfile.TemporaryDirectory(prefix='muckova-release-files-') as directory:
            target = Path(directory) / 'release'
            with patch.multiple(release, RELEASE_DIR=str(target), FILES_TO_COPY=[],
                                STATIC_DIRS=[], CONTENT_DIRS=[],
                                RELEASE_ROOT_FILE_MAPPINGS=sources), contextlib.redirect_stdout(io.StringIO()):
                release.create_release_dir()
                for source, name in sources.items():
                    self.assertEqual((target / name).read_bytes(), original[source])
                self.assertFalse((target / 'backend').exists())
                release.render_release_htaccess('v2026-09+1')
                self.assertEqual((target / '.user.ini').read_bytes(), original[ROOT / 'backend/.user.ini'])
                self.assertIn('X-Site-Release "v2026-09+1"', (target / '.htaccess').read_text())
            for source, content in original.items():
                self.assertEqual(source.read_bytes(), content)


if __name__ == '__main__':
    unittest.main()
