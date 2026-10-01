"""Public RSS search supplies leads only; snippets never establish verification."""
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit

from .http import FetchError


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            key = attrs.get('name') or attrs.get('property') or attrs.get('itemprop')
            if key:
                self.meta.setdefault(key.lower(), []).append(attrs.get('content', ''))
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def search(client, audit, query):
    url = 'https://www.bing.com/search?' + urlencode(dict(format='rss', q=query))
    try:
        root = ET.fromstring(client.get(url, audit, 'public web discovery', query))
    except ET.ParseError:
        raise FetchError('malformed search RSS') from None
    return [dict(url=i.findtext('link', ''), title=i.findtext('title', '')) for i in root.findall('.//item')][:6]


def inspect(client, audit, url):
    p = MetadataParser()
    p.feed(client.get(url, audit, 'original public page metadata inspection'))
    return p.meta, ' '.join(p.parts)


OFFICIAL_PUBLISHERS = ('nature.com', 'springer.com', 'springeropen.com', 'biomedcentral.com',
                       'sciencedirect.com', 'elsevier.com', 'onlinelibrary.wiley.com', 'academic.oup.com',
                       'frontiersin.org', 'mdpi.com', 'tandfonline.com', 'journals.sagepub.com',
                       'bmj.com', 'jamanetwork.com', 'science.org', 'jmir.org', 'plos.org',
                       'karger.com', 'liebertpub.com', 'nejm.org', 'cell.com', 'thelancet.com',
                       'acs.org', 'ieee.org', 'lww.com', 'aacrjournals.org', 'aapm.org',
                       'tandfonline.com', 'degruyter.com', 'thieme-connect.com')


def official_publisher(url):
    host = urlsplit(url).hostname or ''
    return any(host == d or host.endswith('.' + d) for d in OFFICIAL_PUBLISHERS)


def citation_metadata(meta, url):
    def first(k):
        return next(iter(meta.get(k, [])), '')
    title, journal = first('citation_title'), first('citation_journal_title')
    if not title or not journal or not official_publisher(url):
        return None
    date = first('citation_publication_date') or first('citation_date')
    year = re.search(r'(?:19|20)\d\d', date)
    return dict(title=title, journal=journal, doi=first('citation_doi'),
                authors=meta.get('citation_author', []), year=year.group() if year else '',
                years=[year.group()] if year else [], volume=first('citation_volume'),
                issue=first('citation_issue'), page=first('citation_firstpage'),
                publication_status='published', work_type='journal-article',
                metadata_url=url, url=url)
