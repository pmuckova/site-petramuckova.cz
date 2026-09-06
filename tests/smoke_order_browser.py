"""Browser-to-PHP smoke test using a disposable server and fake SMTP recorder.

Needs Node + Playwright, optionally PLAYWRIGHT_MODULE and BROWSER_EXECUTABLE.
Pass a temporary output directory as the sole argument to retain QA screenshots.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_order_handler import OrderEndpointTests, ROOT


def main():
    server = OrderEndpointTests
    server.setUpClass()
    try:
        for name in ('cs', 'en', 'de', 'fr', 'it', 'es', 'pl', 'ru', 'ja', 'zh', 'assets',
                     'main.css', 'blog.css', 'shop.css', 'shop.js', 'form.js', 'index.js', 'favicon.ico'):
            (server.root / name).symlink_to(ROOT / name, target_is_directory=(ROOT / name).is_dir())
        output = Path(sys.argv[1]) if len(sys.argv) > 1 else server.root / 'screenshots'
        output.mkdir(parents=True, exist_ok=True)
        subprocess.run(['node', str(ROOT / 'tests/smoke_order_browser.mjs'), server.url.rsplit('/backend/', 1)[0],
                        str(server.mail), str(output)], check=True, env=os.environ)
    finally:
        server.tearDownClass()


if __name__ == '__main__':
    main()
