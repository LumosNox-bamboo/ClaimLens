import re


def update(r, claim, metadata):
    """Freshness uses publication stage, independently of verification status."""
    text = ' '.join(str(claim.get(k, '')) for k in ('title', 'claim_text'))
    accepted = bool(re.search(r'accepted|in press|已接收|已接受|录用', text, re.I))
    online = bool(re.search(r'online first|early access|published online|在线发表', text, re.I))
    published = metadata.get('publication_status') == 'published'
    if published and (accepted or (online and metadata.get('volume') and (metadata.get('page') or metadata.get('article_number')))):
        r['freshness_status'] = 'CV_UPDATE_AVAILABLE'
        r['suggested_cv_update'] = {k: v for k, v in metadata.items() if v and k in ('title', 'authors', 'journal', 'year', 'doi', 'volume', 'issue', 'page', 'article_number', 'publication_status')}
    elif published and not accepted:
        r['freshness_status'] = 'CURRENT'
    return r
