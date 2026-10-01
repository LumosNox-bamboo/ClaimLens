from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from .http import FetchError

BASE = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'


def lookup(client, audit, doi='', title=''):
    query = (doi + '[AID]') if doi else ('"' + title + '"[Title]')
    url = BASE + 'esearch.fcgi?' + urlencode(dict(db='pubmed', term=query, retmax=3, retmode='json'))
    data = client.json(url, audit, 'PubMed identifier/title search', query)
    ids = data.get('esearchresult', {}).get('idlist')
    if not isinstance(ids, list):
        raise FetchError('malformed PubMed result')
    if not ids:
        return []
    url = BASE + 'efetch.fcgi?' + urlencode(dict(db='pubmed', id=','.join(ids), retmode='xml'))
    try:
        root = ET.fromstring(client.get(url, audit, 'PubMed metadata', ','.join(ids)))
    except ET.ParseError:
        raise FetchError('malformed PubMed XML') from None
    out = []
    for article in root.findall('.//PubmedArticle'):
        t = article.find('.//ArticleTitle')
        journal = article.findtext('.//Journal/Title', '')
        doi = next((x.text for x in article.findall('.//ArticleId') if x.get('IdType') == 'doi'), '')
        year = article.findtext('.//JournalIssue/PubDate/Year', '')
        pmid = article.findtext('.//PMID', '')
        out.append(dict(title=''.join(t.itertext()) if t is not None else '', journal=journal,
                        doi=doi, year=year, years=[year] if year else [], authors=[],
                        volume=article.findtext('.//JournalIssue/Volume', ''), issue=article.findtext('.//JournalIssue/Issue', ''),
                        page=article.findtext('.//MedlinePgn', ''), publication_status='published',
                        work_type='journal-article', url='https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/',
                        metadata_url='https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/'))
    return out
