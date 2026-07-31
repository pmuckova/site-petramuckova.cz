import os
import subprocess
import shutil
import sys
import re
import datetime
import html
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

# --- 1. VIRTUAL ENVIRONMENT CHECK ---
VENV_DIR_NAME = ".venv"

def ensure_venv():
  """
  Checks if running inside a virtual environment.
  If not, attempts to find .venv and relaunch the script inside it.
  """
  if sys.prefix != sys.base_prefix:
    return  # We are safe

  print("--- Not running in a virtual environment. Checking for .venv... ---")
  cwd = os.getcwd()
  possible_paths = [
    os.path.join(cwd, VENV_DIR_NAME, "bin", "python"),      # macOS/Linux
    os.path.join(cwd, VENV_DIR_NAME, "Scripts", "python.exe"), # Windows
  ]

  venv_python = None
  for path in possible_paths:
    if os.path.exists(path):
      venv_python = path
      break

  if venv_python:
    print(f"🔄 Found .venv! Relaunching script using: {venv_python}")
    print("-" * 50)
    os.execv(venv_python, [venv_python] + sys.argv)
  else:
    print(f"❌ Error: Could not find '{VENV_DIR_NAME}' folder.")
    print("   Please create it first: python3 -m venv .venv")
    print("   Then install requirements: .venv/bin/pip install beautifulsoup4")
    sys.exit(1)

# Ensure environment BEFORE imports that might be missing
ensure_venv()

# Try to import bs4
try:
  from bs4 import BeautifulSoup
except ImportError:
  print("❌ Error: 'beautifulsoup4' is not installed in your .venv.")
  print("   Please run: .venv/bin/pip install beautifulsoup4")
  sys.exit(1)


# --- CONFIGURATION ---

BASE_URL = "https://www.petramuckova.cz"

# Directories containing the package.json files (Build Tools)
CSS_DIR = 'cssnano'
JS_DIR = 'terser'
HTML_DIR = 'html-minifier'

# The npm arguments to run inside each build-tool directory
NPM_ARGS = ['run', 'build']

# Name of the output directory
RELEASE_DIR = 'release'

# SITEMAP CONFIG
TARGET_SITEMAP_FILES = ['index.html', 'blog.html']
XMLNS = "http://www.sitemaps.org/schemas/sitemap/0.9"
XMLNS_XHTML = "http://www.w3.org/1999/xhtml"
XMLNS_IMAGE = "http://www.google.com/schemas/sitemap-image/1.1"
XMLNS_VIDEO = "http://www.google.com/schemas/sitemap-video/1.1"

# 1. Single files to COPY from root to release/
# Removed 'sitemap.xml' because we generate it dynamically now
FILES_TO_COPY = [
  'favicon.ico',
  'robots.txt',
  'seznam-wmt-7V6YpmPOnIbLdpFwNckOL62U7QqrxcpT.txt',
  'seznam-wmt-O4b3QDTdq0BIdWrcCoI9I5nqGiYObYhJ.txt',
  'seznam-wmt-QFuSXDQWAGwnLU1ZLgPbQLc7hOBEagVE.txt',
  'seznam-wmt-XHLjQ4Fw7qAJj5SlvYqiVkfXyuTnpAUT.txt',
  'BingSiteAuth.xml'
]

# Files stored outside the public root in the source tree, but copied to the
# release root under a different name.
RELEASE_ROOT_FILE_MAPPINGS = {
  os.path.join('backend', '.htaccess'): '.htaccess'
}

RELEASE_VERSION_PLACEHOLDER = '{{RELEASE_VERSION}}'
RELEASE_VERSION_URL_PLACEHOLDER = '{{RELEASE_VERSION_URL}}'

# 2. Directories to COPY entirely (Structure + Content preserved)
STATIC_DIRS = [
  'assets'
]

# 3. Directories to PROCESS (Recursive copy with exclusions)
# We also use this list for Sitemap generation
CONTENT_DIRS = [
  'cs', 'en', 'de', 'fr', 'it', 'es', 'pl', 'ru', 'ja', 'zh'
]

# --- CLASSES ---

class PageRecord:
  def __init__(self, file_path, lang, relative_url):
    self.file_path = file_path
    self.lang = lang
    self.relative_url = relative_url
    self.loc = f"{BASE_URL}/{relative_url}"
    self.lastmod = self._get_lastmod()
    self.images = []
    self.videos = []

    # Priority settings
    if "index.html" in file_path:
      self.priority = "1.0"
    else:
      self.priority = "0.8"

    self.changefreq = "monthly"

  def _get_lastmod(self):
    return datetime.datetime.now().strftime('%Y-%m-%d')
    # try:
    #   timestamp = os.path.getmtime(self.file_path)
    #   return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
    # except OSError:
    #   return datetime.datetime.now().strftime('%Y-%m-%d')

  def parse_content(self):
    """Parses HTML to extract images and videos."""
    with open(self.file_path, 'r', encoding='utf-8') as f:
      content = f.read()
      soup = BeautifulSoup(content, 'html.parser')

    # --- 1. IMAGE EXTRACTION ---
    for img in soup.find_all('img'):
      src = img.get('src')
      if not src:
        continue

      if 'icon' in src or 'logo' in src:
        continue

      full_img_url = self._resolve_url(src)
      title = img.get('title') or img.get('alt') or ""
      caption = ""

      figure = img.find_parent('figure')
      if figure:
        figcaption = figure.find('figcaption')
        if figcaption:
          caption = figcaption.get_text(strip=True)

      if not title:
        frame = img.find_parent(class_='tech-frame') or img.find_parent(class_='team-visual')
        if frame:
          body = frame.find_next_sibling('div')
          if body and body.find('h3'):
            title = body.find('h3').get_text(strip=True)

      # Enforce both title and caption
      if not title and caption: title = caption
      elif not caption and title: caption = title
      elif not title and not caption:
        title = "Image"
        caption = "Image"

      self.images.append({
        'loc': full_img_url,
        'title': title[:250],
        'caption': caption[:1000]
      })

    # --- 2. VIDEO EXTRACTION ---
    for iframe in soup.find_all('iframe'):
      src = iframe.get('src', '')
      if 'youtube' in src or 'youtu.be' in src:
        video_id = self._extract_youtube_id(src)
        if video_id:
          vid_title = "Video"
          vid_desc = "Video Content"

          article_card = iframe.find_parent(class_='blog-card')
          if article_card:
            header = article_card.find('header')
            if header:
              h1 = header.find('h1')
              if h1: vid_title = h1.get_text(strip=True)
              lead = header.find(class_='lead')
              if lead: vid_desc = lead.get_text(strip=True)

          self.videos.append({
            'thumbnail_loc': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            'title': vid_title,
            'description': vid_desc,
            'player_loc': src
          })

  def _resolve_url(self, src):
    clean_src = src.strip()
    clean_src = clean_src.replace('../', '').replace('./', '')
    if clean_src.startswith('/'):
      clean_src = clean_src[1:]

    if clean_src.startswith('http'):
      return clean_src
    return f"{BASE_URL}/{clean_src}"

  def _extract_youtube_id(self, url):
    match = re.search(r'/embed/([a-zA-Z0-9_-]+)', url)
    if match:
      return match.group(1)
    return None

def escape_xml(data):
  if not data: return ""
  return data.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')


# --- BUILD FUNCTIONS ---

def _tool_version(executable, environment):
  """Returns a command's version string without changing the active process."""
  try:
    result = subprocess.run(
      [executable, '--version'],
      env=environment,
      capture_output=True,
      text=True,
      check=True
    )
    return result.stdout.strip()
  except (OSError, subprocess.CalledProcessError):
    return 'unknown'

def ensure_node_tooling():
  """Finds Node/npm on PATH or activates an installed NVM Node version."""
  print("\n🔎 Checking Node.js tooling...")

  environment = os.environ.copy()
  node_executable = shutil.which('node', path=environment.get('PATH'))
  npm_executable = shutil.which('npm', path=environment.get('PATH'))

  if node_executable and npm_executable:
    print(f"   ✅ Node.js {_tool_version(node_executable, environment)}")
    print(f"   ✅ npm {_tool_version(npm_executable, environment)}")
    return npm_executable, environment

  nvm_dir = os.path.expanduser(environment.get('NVM_DIR', '~/.nvm'))
  nvm_script = os.path.join(nvm_dir, 'nvm.sh')
  shell_executable = shutil.which('bash') or shutil.which('zsh')

  if not shell_executable or not os.path.isfile(nvm_script):
    print("   ❌ Error: Node.js/npm are not on PATH and NVM could not be loaded.")
    print(f"      Expected NVM script: {nvm_script}")
    sys.exit(1)

  nvm_environment = environment.copy()
  nvm_environment['NVM_DIR'] = nvm_dir
  nvm_command = r'''
    . "$NVM_DIR/nvm.sh"
    if nvm use --silent >/dev/null 2>&1; then
      :
    elif nvm use default --silent >/dev/null 2>&1; then
      :
    elif nvm use --lts --silent >/dev/null 2>&1; then
      :
    else
      exit 1
    fi
    command -v node
    command -v npm
  '''

  try:
    result = subprocess.run(
      [shell_executable, '-c', nvm_command],
      cwd=os.getcwd(),
      env=nvm_environment,
      capture_output=True,
      text=True,
      check=True
    )
  except (OSError, subprocess.CalledProcessError):
    print("   ❌ Error: NVM was found, but no usable project, default, or LTS Node.js version is installed.")
    sys.exit(1)

  resolved_paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
  if len(resolved_paths) < 2:
    print("   ❌ Error: NVM loaded, but Node.js/npm paths could not be resolved.")
    sys.exit(1)

  node_executable, npm_executable = resolved_paths[-2:]
  node_bin_dir = os.path.dirname(node_executable)
  current_path = nvm_environment.get('PATH', '')
  nvm_environment['PATH'] = os.pathsep.join(filter(None, [node_bin_dir, current_path]))

  if not os.path.isfile(node_executable) or not os.path.isfile(npm_executable):
    print("   ❌ Error: NVM returned invalid Node.js/npm executable paths.")
    sys.exit(1)

  print(f"   ✅ Loaded Node.js {_tool_version(node_executable, nvm_environment)} through NVM")
  print(f"   ✅ Loaded npm {_tool_version(npm_executable, nvm_environment)} through NVM")
  return npm_executable, nvm_environment

def run_npm_in_dir(directory, npm_executable, environment):
  """Runs the configured npm command inside a specific directory."""
  display_command = 'npm ' + ' '.join(NPM_ARGS)
  print(f"📂 Entering directory: ./{directory}")
  print(f"   🚀 Running: '{display_command}'...")

  if not os.path.isdir(directory):
    print(f"   ❌ Error: Directory '{directory}' not found.")
    sys.exit(1)

  try:
    subprocess.run(
      [npm_executable, *NPM_ARGS],
      cwd=directory,
      env=environment,
      check=True
    )
    print("   ✅ Success.")
  except subprocess.CalledProcessError:
    print(f"   ❌ Error: Command failed in {directory}.")
    sys.exit(1)

def create_release_dir():
  """Copies files to the release directory."""
  print(f"\n📦 Creating release directory: ./{RELEASE_DIR}...")

  # 1. Clean and Create Release Directory
  if os.path.exists(RELEASE_DIR):
    print(f"   - Cleaning existing '{RELEASE_DIR}' directory...")
    shutil.rmtree(RELEASE_DIR)
  os.makedirs(RELEASE_DIR)

  # 2. EXPLICITLY CREATE LANGUAGE DIRECTORIES
  print("   + Creating language structure...")
  for lang in CONTENT_DIRS:
    lang_path = os.path.join(RELEASE_DIR, lang)
    if not os.path.exists(lang_path):
      os.makedirs(lang_path)

  # 3. Copy Root Files
  print("   + Copying root files...")
  for filename in FILES_TO_COPY:
    if os.path.exists(filename):
      dest = os.path.join(RELEASE_DIR, filename)
      shutil.copy2(filename, dest)
      print(f"     -> Copied: {filename}")
    else:
      print(f"     ⚠️  Warning: Source file not found: {filename}")

  # 4. Copy mapped files to the release root
  print("   + Copying release-root configuration files...")
  for source, destination in RELEASE_ROOT_FILE_MAPPINGS.items():
    if os.path.exists(source):
      dest = os.path.join(RELEASE_DIR, destination)
      shutil.copy2(source, dest)
      print(f"     -> Copied: {source} -> {destination}")
    else:
      print(f"     ⚠️  Warning: Source file not found: {source}")

  # 5. Copy Static Directories
  print("   + Copying static directories...")
  for directory in STATIC_DIRS:
    if os.path.exists(directory):
      dest_dir = os.path.join(RELEASE_DIR, directory)
      shutil.copytree(directory, dest_dir)
      print(f"     -> Copied whole directory: {directory}/")
    else:
      print(f"     ⚠️  Warning: Static directory not found: {directory}/")

  # 6. Process Content Directories
  print("   + Processing content directories...")
  for directory in CONTENT_DIRS:
    if os.path.exists(directory):
      print(f"     -> Processing: {directory}/")

      # Walk through the source directory
      for root, dirs, files in os.walk(directory):
        relative_path = os.path.relpath(root, os.getcwd())
        target_dir = os.path.join(RELEASE_DIR, relative_path)

        if not os.path.exists(target_dir):
          os.makedirs(target_dir)

        for file in files:
          source_file = os.path.join(root, file)
          dest_file = os.path.join(target_dir, file)
          shutil.copy2(source_file, dest_file)
    else:
      pass

  print(f"\n🎉 Success! Files copied to: {os.path.abspath(RELEASE_DIR)}")

def render_release_htaccess(version=None):
  """Replaces release metadata placeholders in the copied .htaccess file."""
  print("\n🏷️  Rendering release metadata in .htaccess...")

  htaccess_path = os.path.join(RELEASE_DIR, '.htaccess')
  if not os.path.isfile(htaccess_path):
    print(f"   ❌ Error: Release configuration not found: {htaccess_path}")
    sys.exit(1)

  with open(htaccess_path, 'r', encoding='utf-8') as f:
    content = f.read()

  if not version:
    filtered_lines = [
      line for line in content.splitlines()
      if RELEASE_VERSION_PLACEHOLDER not in line
    ]
    rendered_content = '\n'.join(filtered_lines) + '\n'
    rendered_content = rendered_content.replace(
      f'?v={RELEASE_VERSION_URL_PLACEHOLDER}',
      ''
    )
    print("   ℹ️  No target version provided; the release header was omitted and redirects remain unversioned.")
  else:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/+@-]*', version):
      print(f"   ❌ Error: Invalid target version for .htaccess metadata: {version!r}")
      sys.exit(1)

    missing_placeholders = [
      placeholder for placeholder in (
        RELEASE_VERSION_PLACEHOLDER,
        RELEASE_VERSION_URL_PLACEHOLDER
      )
      if placeholder not in content
    ]
    if missing_placeholders:
      print("   ❌ Error: Required release-version placeholders are missing from backend/.htaccess.")
      sys.exit(1)

    rendered_content = content.replace(RELEASE_VERSION_PLACEHOLDER, version)
    rendered_content = rendered_content.replace(
      RELEASE_VERSION_URL_PLACEHOLDER,
      quote(version, safe='')
    )
    print(f"   ✅ Added X-Site-Release: {version}")
    print(f"   ✅ Added version '{version}' to all root language redirects")

  with open(htaccess_path, 'w', encoding='utf-8') as f:
    f.write(rendered_content)

def update_asset_paths(asset_ref=None):
  """Updates /assets/ paths to jsDelivr CDN URLs in HTML and CSS files."""
  print("\n🔗 Updating asset paths to CDN in release files...")

  base_cdn = "https://cdn.jsdelivr.net/gh/pmuckova/site-petramuckova.cz"

  if asset_ref:
    print(f"   ℹ️  Asset ref provided: '{asset_ref}'. Using it for jsDelivr URLs.")
    base_cdn += f"@{asset_ref}"
  else:
    print("   ℹ️  No asset ref provided. Using default (latest) CDN URLs.")

  replacements = {
    '/assets/desktop/': f'{base_cdn}/assets/desktop/',
    '/assets/800/': f'{base_cdn}/assets/800/',
    '/assets/1200/': f'{base_cdn}/assets/1200/'
  }

  count = 0
  for root, dirs, files in os.walk(RELEASE_DIR):
    for file in files:
      if file.endswith(('.html', '.css')):
        file_path = os.path.join(root, file)
        try:
          with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

          new_content = content
          for target, replacement in replacements.items():
            pattern = r'([\"\s\'\(])' + re.escape(target)
            new_content = re.sub(pattern, r'\1' + replacement, new_content)

          if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
              f.write(new_content)
            count += 1
        except Exception as e:
          print(f"     ❌ Error processing {file}: {e}")

  print(f"   ✅ Updated asset paths in {count} files.")

def append_version_to_public_urls(version=None):
  """Adds the release version to same-site navigation URLs in release HTML."""
  print("\n🏷️  Adding the release version to public navigation URLs...")

  if not version:
    print("   ℹ️  No target version provided. Public navigation URLs were not changed.")
    return

  if version.lower() in ('main', 'master'):
    print("   ⚠️  The target is a mutable branch name, so its URL cache key will not change between releases.")

  public_hosts = {'petramuckova.cz', 'www.petramuckova.cz'}
  language_pattern = '|'.join(re.escape(lang) for lang in CONTENT_DIRS)
  public_page_pattern = re.compile(
    rf'/(?:{language_pattern})(?:/?|/(?:index|blog)(?:\.html)?)'
  )
  anchor_href_pattern = re.compile(
    r'(?P<prefix><a\b[^>]*?\bhref\s*=\s*)(?P<quote>["\'])(?P<url>.*?)(?P=quote)',
    re.IGNORECASE
  )

  def add_version(url):
    decoded_url = html.unescape(url)
    parsed = urlsplit(decoded_url)

    if parsed.scheme and parsed.scheme.lower() not in ('http', 'https'):
      return url
    if parsed.hostname and parsed.hostname.lower() not in public_hosts:
      return url
    if not parsed.hostname and not parsed.path.startswith('/'):
      return url
    if not public_page_pattern.fullmatch(parsed.path):
      return url

    query = [
      (key, value)
      for key, value in parse_qsl(parsed.query, keep_blank_values=True)
      if key != 'v'
    ]
    query.append(('v', version))

    versioned_url = urlunsplit((
      parsed.scheme,
      parsed.netloc,
      parsed.path,
      urlencode(query),
      parsed.fragment
    ))
    return html.escape(versioned_url, quote=False)

  updated_files = 0
  updated_urls = 0

  for root, dirs, files in os.walk(RELEASE_DIR):
    for file in files:
      if not file.endswith('.html'):
        continue

      file_path = os.path.join(root, file)
      try:
        with open(file_path, 'r', encoding='utf-8') as f:
          content = f.read()

        file_url_count = 0

        def replace_anchor_href(match):
          nonlocal file_url_count
          original_url = match.group('url')
          versioned_url = add_version(original_url)
          if versioned_url == original_url:
            return match.group(0)

          file_url_count += 1
          return (
            f"{match.group('prefix')}{match.group('quote')}"
            f"{versioned_url}{match.group('quote')}"
          )

        new_content = anchor_href_pattern.sub(replace_anchor_href, content)

        if new_content != content:
          with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
          updated_files += 1
          updated_urls += file_url_count
      except Exception as e:
        print(f"     ❌ Error processing {file}: {e}")

  print(f"   ✅ Added version '{version}' to {updated_urls} public URLs in {updated_files} files.")

def generate_sitemap():
  """Generates sitemap.xml by scanning the SOURCE content directories."""
  print("\n🗺️  Generating sitemap.xml...")

  root_dir = os.getcwd()
  pages_by_type = {}

  # We iterate only through the configured CONTENT_DIRS (cs, en, de...)
  for lang_code in CONTENT_DIRS:
    dir_path = os.path.join(root_dir, lang_code)

    if os.path.exists(dir_path):
      for target_file in TARGET_SITEMAP_FILES:
        file_path = os.path.join(dir_path, target_file)
        if os.path.exists(file_path):

          if target_file == 'index.html':
            # rel_url = f"{lang_code}/"
            rel_url = f"{lang_code}/{target_file}"
            group_key = 'index'
          else:
            clean_name = target_file.replace('.html', '')
            # rel_url = f"{lang_code}/{clean_name}"
            rel_url = f"{lang_code}/{target_file}"
            group_key = clean_name

          # Parse Source File
          record = PageRecord(file_path, lang_code, rel_url)
          record.parse_content()

          if group_key not in pages_by_type:
            pages_by_type[group_key] = []
          pages_by_type[group_key].append(record)

          print(f"     -> Indexed: {lang_code}/{target_file}")

  # Build XML
  xml_lines = []
  xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
  xml_lines.append(f'<urlset xmlns="{XMLNS}" xmlns:xhtml="{XMLNS_XHTML}" xmlns:image="{XMLNS_IMAGE}" xmlns:video="{XMLNS_VIDEO}">')

  for group_key, records in pages_by_type.items():
    for page in records:
      xml_lines.append('  <url>')
      xml_lines.append(f'    <loc>{escape_xml(page.loc)}</loc>')
      xml_lines.append(f'    <lastmod>{page.lastmod}</lastmod>')
      xml_lines.append(f'    <changefreq>{page.changefreq}</changefreq>')
      xml_lines.append(f'    <priority>{page.priority}</priority>')
      xml_lines.append(f'    <xhtml:link rel="canonical" href="{escape_xml(page.loc).replace('/index.html', '').replace('.html', '')}" />')

      # Alternates (Hreflang)
      for alt_page in records:
        xml_lines.append(f'    <xhtml:link rel="alternate" hreflang="{alt_page.lang}" href="{escape_xml(alt_page.loc)}" />')
        xml_lines.append(f'    <xhtml:link rel="alternate" hreflang="{alt_page.lang}" href="{escape_xml(alt_page.loc.replace('/index.html', '').replace('.html', ''))}" />')

      # X-Default
      x_default = next((p for p in records if p.lang == 'cs'), records[0])
      xml_lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{escape_xml(x_default.loc)}" />')
      xml_lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{escape_xml(x_default.loc.replace('/index.html', '').replace('.html', ''))}" />')

      # Images
      for img in page.images:
        xml_lines.append('    <image:image>')
        xml_lines.append(f'      <image:loc>{escape_xml(img["loc"])}</image:loc>')
        xml_lines.append(f'      <image:title>{escape_xml(img["title"])}</image:title>')
        xml_lines.append(f'      <image:caption>{escape_xml(img["caption"])}</image:caption>')
        xml_lines.append('    </image:image>')

      # Videos
      for vid in page.videos:
        xml_lines.append('    <video:video>')
        xml_lines.append(f'      <video:thumbnail_loc>{escape_xml(vid["thumbnail_loc"])}</video:thumbnail_loc>')
        xml_lines.append(f'      <video:title>{escape_xml(vid["title"])}</video:title>')
        xml_lines.append(f'      <video:description>{escape_xml(vid["description"])}</video:description>')
        xml_lines.append(f'      <video:player_loc>{escape_xml(vid["player_loc"])}</video:player_loc>')
        xml_lines.append('    </video:video>')

      xml_lines.append('  </url>')

  xml_lines.append('</urlset>')

  with open('sitemap.xml', 'w', encoding='utf-8') as f:
    f.write('\n'.join(xml_lines))

  print(f"   ✅ Generated sitemap.xml in {RELEASE_DIR} with {sum(len(v) for v in pages_by_type.values())} URLs.")

def parse_release_arguments():
  """Parses the jsDelivr asset ref and the independent site release version."""
  if len(sys.argv) != 3:
    print("❌ Error: Two release arguments are required.")
    print("   Usage: python3 release.py <asset-ref> <site-version>")
    print("   Example: python3 release.py main 1.0.3")
    sys.exit(1)

  asset_ref = sys.argv[1].strip()
  site_version_input = sys.argv[2].strip()

  version_token_pattern = r'[A-Za-z0-9][A-Za-z0-9._/+@-]*'
  if not re.fullmatch(version_token_pattern, asset_ref):
    print(f"❌ Error: Invalid jsDelivr asset ref: {asset_ref!r}")
    sys.exit(1)
  if not re.fullmatch(version_token_pattern, site_version_input):
    print(f"❌ Error: Invalid site release version: {site_version_input!r}")
    sys.exit(1)

  site_version = (
    site_version_input
    if site_version_input.lower().startswith('v')
    else f'v{site_version_input}'
  )

  print("\n📌 Release configuration:")
  print(f"   - jsDelivr asset ref: {asset_ref}")
  print(f"   - Site release version: {site_version}")
  return asset_ref, site_version

if __name__ == "__main__":
  asset_ref, site_version = parse_release_arguments()

  # Resolve Node.js/npm before replacing an existing release.
  npm_executable, node_environment = ensure_node_tooling()

  # 1. Create Release Folder
  create_release_dir()

  # Render the release version into the copied server configuration.
  render_release_htaccess(site_version)

  # 2. Run CSS Build
  run_npm_in_dir(CSS_DIR, npm_executable, node_environment)

  # 3. Run JS Build
  run_npm_in_dir(JS_DIR, npm_executable, node_environment)

  # 4. Generate Sitemap (New Step)
  generate_sitemap()

  # 5. Run HTML Build
  run_npm_in_dir(HTML_DIR, npm_executable, node_environment)

  # 6. Update Asset Paths to CDN
  update_asset_paths(asset_ref)

  # 7. Add the site release version to same-site navigation URLs
  append_version_to_public_urls(site_version)
