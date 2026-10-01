from urllib.parse import quote, urlencode

from .http import FetchError


def metadata(item):
    if not isinstance(item, dict) or not item.get('DOI') or not isinstance(item.get('title'), list):
        raise FetchError('malformed Crossref work')
    years = []
    for key in ('published', 'published-print', 'published-online', 'issued'):
        date = item.get(key, {}).get('date-parts', [])
        if date and date[0]:
            years.append(str(date[0][0]))
    return dict(title=' '.join(item.get('title', [])), journal=' '.join(item.get('container-title', [])),
                doi=item['DOI'], authors=[(a.get('given', '') + ' ' + a.get('family', '')).strip() for a in item.get('author', [])],
                year=years[0] if years else '', years=list(set(years)), volume=item.get('volume', ''),
                issue=item.get('issue', ''), page=item.get('page', ''), article_number=item.get('article-number', ''),
                publication_status='published' if item.get('type') == 'journal-article' and years else item.get('type', 'unknown'),
                work_type=item.get('type', ''), publisher=item.get('publisher', ''), url=item.get('URL', ''),
                metadata_url='https://api.crossref.org/works/' + quote(item['DOI'], safe=''))


def lookup(client, audit, doi='', title=''):
    if doi:
        url = 'https://api.crossref.org/works/' + quote(doi, safe='')
        data = client.json(url, audit, 'DOI exact match', doi)
        return [metadata(data.get('message'))]
    url = 'https://api.crossref.org/works?' + urlencode({'query.title': title, 'rows': 3})
    data = client.json(url, audit, 'title metadata search', title)
    items = data.get('message', {}).get('items')
    if not isinstance(items, list):
        raise FetchError('malformed Crossref search')
    return [metadata(item) for item in items]
