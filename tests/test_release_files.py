import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import release


class ReleaseFileTests(unittest.TestCase):
    @contextlib.contextmanager
    def build(self, sources, **settings):
        # Every source and output is disposable; never clean the real release/.
        with tempfile.TemporaryDirectory(prefix='muckova-release-files-') as directory:
            root = Path(directory)
            for name, content in sources.items():
                source = root / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(content, encoding='utf-8')
            options = {'RELEASE_DIR': 'release', 'STATIC_DIRS': ['assets'], 'CONTENT_DIRS': ['cs'], **settings}
            with contextlib.chdir(root), patch.multiple(release, **options), contextlib.redirect_stdout(io.StringIO()):
                release.create_release_dir()
                yield root, root / 'release'
            for name, content in sources.items():
                self.assertEqual((root / name).read_text(encoding='utf-8'), content)

    def assert_frontend_files(self, target, expected):
        self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}, set(expected))
        self.assertFalse((target / 'backend').exists())

    def test_release_requires_no_backend_files(self):
        sources = {'robots.txt': 'robots', 'cs/index.html': '<h1>Home</h1>', 'assets/photo.jpg': 'photo'}
        with self.build(sources) as (root, target):
            self.assert_frontend_files(target, sources)
            self.assertFalse((root / 'backend').exists())

    def test_explicit_root_copy_excludes_php_and_server_configuration(self):
        sources = {'robots.txt': 'robots', '.htaccess': 'apache', '.user.ini': 'php settings',
                   'order.php': '<?php', 'handler.PHP': '<?php', 'legacy.php8': '<?php',
                   'template.phtml': '<?php', 'archive.phar': 'php archive', 'order.php.bak': '<?php',
                   'backend/README.txt': 'private backend file'}
        with self.build(sources, FILES_TO_COPY=list(sources)) as (_, target):
            self.assert_frontend_files(target, ['robots.txt'])

    def test_recursive_copies_exclude_backend_files_at_every_depth(self):
        sources = {}
        for directory in ('assets', 'cs'):
            sources.update({
                f'{directory}/public.txt': 'public',
                f'{directory}/nested/public.txt': 'also public',
                f'{directory}/handler.php': '<?php',
                f'{directory}/nested/handler.PHP': '<?php',
                f'{directory}/.htaccess': 'apache',
                f'{directory}/nested/.user.ini': 'php settings',
                f'{directory}/backend/config.json': 'private',
                f'{directory}/nested/backend/template.html': 'private template',
            })
        with self.build(sources) as (_, target):
            self.assert_frontend_files(target, ['assets/public.txt', 'assets/nested/public.txt',
                                                'cs/public.txt', 'cs/nested/public.txt'])
            self.assertFalse(any(p.name == 'backend' for p in target.rglob('*')))

    def test_backend_cannot_be_added_as_a_static_or_content_directory(self):
        for setting in ('STATIC_DIRS', 'CONTENT_DIRS'):
            with self.subTest(setting=setting), self.build({'backend/config.json': 'private'}, **{setting: ['backend']}) as (_, target):
                self.assert_frontend_files(target, [])

    def test_rebuild_does_not_keep_stale_backend_files(self):
        with self.build({'robots.txt': 'robots'}) as (_, target):
            (target / 'backend').mkdir()
            (target / 'backend/order.php').write_text('stale PHP')
            (target / '.htaccess').write_text('stale apache settings')
            (target / '.user.ini').write_text('stale PHP settings')
            release.create_release_dir()
            self.assert_frontend_files(target, ['robots.txt'])


if __name__ == '__main__':
    unittest.main()
