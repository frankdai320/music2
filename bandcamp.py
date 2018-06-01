"""Make a custom Bandcamp 'embed'."""

import re
import sys
from json import loads

from google.appengine.api import urlfetch

if sys.version_info[0] >= 3:  # major version
    from urllib.parse import urlparse
else:
    from urlparse import urlparse

INFO_PATTERN = re.compile(r'trackinfo:\s+(.+),')
ART_PATTERN = re.compile(r'<a class="popupImage" href="([\w./:]+)">')


def get_info(url):
    if not from_host(url, 'bandcamp.com'):
        return {}
    try:
        page = urlfetch.fetch(url)
    except Exception:
        return {}

    search = INFO_PATTERN.search(page.content)
    if not search:
        return {}
    try:
        info = loads(search.group(1))
    except Exception:
        return {}

    if len(info) == 0:
        return {}

    info = info[0]

    art = ART_PATTERN.search(page.content)
    if art:
        info['albumArt'] = art.group(1)

    return info


def find_raw_link(info):
    """Get a raw audio link from the info returned by get_info()."""
    file_info = info.get('file')

    if not file_info:
        return

    return file_info.get('mp3-128')


def from_host(url, host):
    parsed_url = urlparse(url)
    host = host.lower()

    return parsed_url.netloc.lower().endswith('.' + host) or parsed_url.netloc.lower() == host
