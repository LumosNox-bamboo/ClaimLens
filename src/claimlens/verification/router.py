from __future__ import annotations

import re
from urllib.parse import quote

from .evidence import apply, evidence, norm, title_match
from .freshness import update
from .models import Status, result, validate_result
from .providers import crossref, pubmed, web
from .providers.http import FetchError

DOC_TYPES = {'education', 'professional_qualification', 'certification'}
HEADINGS = re.compile(r'^(?:selected\s+)?(?:publications?|published articles|patents?|honors?(?:\s*&?\s*awards?)?|awards?|conference presentations?(?: and awards?)?|科研成果|发表论文|论文发表|专利|获奖情况|奖励荣誉|学术成果)[\s:：]*$', re.I)


def safe_text(text):
    # Never search candidate/application IDs, local paths, contact details or placeholders.
    text = re.sub(r'\bC-[A-F0-9]{6}(?:-\d+)?\b|[\w.+-]+@[\w.-]+\.[A-Za-z]+|https?://\S+|/Users/\S+', '', text)
    text = re.sub(r'\[(?:REDACTED|PERSON|NAME|PHONE|EMAIL|ID)[^\]]*\]|<[^>]*>', '', text, flags=re.I)
    text = re.sub(r'(?<!\d)(?:\+?\d[\s-]*){10,}(?!\d)', '', text)
    return ' '.join(text.split()).strip('• ;；')


def public_title(claim):
    text = safe_text(claim.get('title', ''))
    text = re.sub(r'^\s*\d+[.)、]\s*', '', text)
    text = re.split(r'\bdoi\s*[:：]|\(\s*(?:IF|impact factor)\s*[=:]|\[J\]|\[Conference Abstract\]', text, flags=re.I)[0]
    text = re.split(r'\bAccepted for publication|\bPublished online|\bIn press', text, flags=re.I)[0]
    # A leading author citation is removed, rather than transmitted as a whole claim.
    parts = re.split(r'\.\s+', text)
    while len(parts) > 1 and (len(parts[0].split()) < 5 or re.search(r'(?:\bet al\b|,\s*[A-Z]\b|\b[A-Z]\.,)', parts[0]) or re.match(r'^[A-Z][a-zA-Z-]+\s+[A-Z]{1,4}(?:[ ,;]|$)', parts[0])):
        parts.pop(0)
    if parts:
        text = parts[0]
    text = re.sub(r'\s+(?:19|20)\d\d(?:[;,].*)?$', '', text)
    return text.strip(' .;；')[:240]


def usable_title(text):
    if not text or HEADINGS.fullmatch(text):
        return False
    if re.search(r'熟练|撰写能力|文献检索|科研思维|发表.*篇|共.*篇|论文.*篇|publication list|impact factor|^doi:|^Published\s+\d|^no\.', text, re.I):
        return False
    return len(re.findall(r'[A-Za-z]+', text)) >= 5 or len(re.findall(r'[\u4e00-\u9fff]', text)) >= 10


def audit_for(claim, cid):
    return dict(candidate_id=cid, claim_id=claim['claim_id'], search_queries=[],
                sources_considered=[], sources_rejected=[], search_attempt_count=0,
                final_decision_reason='', rejection_reason=None)


class Router:
    def __init__(self, client, metrics):
        self.client, self.metrics = client, metrics

    def verify(self, claim, cid):
        audit = audit_for(claim, cid)
        r = result(claim)
        try:
            t = claim['claim_type']
            if t in DOC_TYPES:
                r['verification_status'] = Status.DOCUMENT_REQUIRED.value
                r['verification_notes'] = 'No public personal record or lawful public registry identifier is supplied. Request the relevant diploma, licence or certificate. Institution/course existence cannot establish individual completion.'
            elif t == 'publication':
                r = self.publication(claim, r, audit)
            elif t == 'patent':
                r = self.patent(claim, r, audit)
            elif t in {'award', 'competition', 'conference_presentation'}:
                r = self.event(claim, r, audit)
            else:
                r['verification_notes'] = 'Unsupported claim type requires manual review.'
        except (FetchError, ValueError, TypeError, KeyError) as exc:
            r['verification_status'] = Status.NEEDS_REVIEW.value
            r['verification_notes'] = 'Provider result could not be safely interpreted: ' + type(exc).__name__ + '. No adverse inference.'
            audit['provider_error'] = type(exc).__name__
        audit['final_decision_reason'] = r['verification_notes']
        validate_result(r)
        return r, audit

    def compare_publication(self, claim, r, audit, m, name, strength='A'):
        qtitle = public_title(claim)
        supplied_doi = claim.get('doi', '').casefold().strip()
        exact_doi = bool(supplied_doi and supplied_doi == m.get('doi', '').casefold())
        exact_title = usable_title(qtitle) and title_match(qtitle, re.sub(r'^\d{1,6}\s+', '', m['title']))
        fragment = bool(qtitle and len(norm(qtitle)) > 20 and norm(qtitle) in norm(m['title']))
        if not (exact_doi or exact_title):
            audit['sources_rejected'].append(dict(url=m['metadata_url'], rejection_reason='Core title/DOI not linked; a truncated or generic title fragment cannot uniquely identify a work'))
            return False
        matched, conflicts = [], []
        if exact_doi:
            matched.append('doi')
        if exact_title:
            matched.append('title')
        elif fragment:
            matched.append('title_fragment')
        elif exact_doi and usable_title(qtitle):
            # Conflicts are only inferred from an apparently complete, specific title.
            if len(qtitle.split()) >= 8 and not re.match(r'^[a-z]|^(?:Medicine|Dermatol|Published|Oct|no\.)\b', qtitle):
                conflicts.append('title')
        if claim.get('year'):
            years = m.get('years', [])
            if str(claim['year']) in years:
                matched.append('year')
            elif years and not re.search(r'accepted|in press|录用|接收', claim.get('claim_text', '') + claim.get('title', ''), re.I):
                # Online/print year differences alone are not a substantive conflict.
                if min(abs(int(y) - int(claim['year'])) for y in years if str(y).isdigit()) > 1:
                    conflicts.append('year')
        if claim.get('journal'):
            if norm(claim['journal']) == norm(m.get('journal', '')):
                matched.append('journal')
            elif m.get('journal'):
                conflicts.append('journal')
        if claim.get('authors'):
            # Exact supplied list only; never recover candidate identity from authors.
            if norm(claim['authors']) == norm(' '.join(m.get('authors', []))):
                matched.append('authors')
        matched.append('publication_status')
        e = evidence(name, 'structured_publication_metadata', m['metadata_url'], strength,
                     matched, conflicts, 'Public work metadata inspected; candidate authorship is not established unless explicitly supplied and matched.')
        e['verified_metadata'] = {k: v for k, v in m.items() if k not in ('metadata_url', 'url', 'years') and v}
        apply(r, e)
        if conflicts:
            r['verification_status'] = Status.CONFLICT.value
            r['verification_notes'] = 'Reliable work metadata has a substantive conflict in: ' + ', '.join(conflicts) + '. Review the supplied claim and source; no candidate-level inference.'
        elif exact_title and not r['unverified_fields']:
            r['verification_status'] = Status.VERIFIED.value
            r['verification_notes'] = 'Strong public source matches the supplied core bibliographic fields. This verifies the work, not an unstated candidate-author relationship.'
        else:
            r['verification_status'] = Status.PARTIALLY_VERIFIED.value
            r['verification_notes'] = 'The public work is linked by DOI or title, but supplied citation text is incomplete or some fields remain unverified. No authorship inferred.'
        # claim_text is an input container, not a separate factual field when exact citation matches.
        if exact_title and claim.get('claim_text') == claim.get('title'):
            r['unverified_fields'] = [f for f in r['unverified_fields'] if f != 'claim_text']
            if not conflicts and not r['unverified_fields']:
                r['verification_status'] = Status.VERIFIED.value
        update(r, claim, m)
        r['journal_metrics'] = self.metrics.lookup(m.get('journal', ''), audit)
        return True

    def publication(self, claim, r, audit):
        doi, title = claim.get('doi', '').strip(), public_title(claim)
        if not doi and not usable_title(title):
            r['verification_notes'] = 'The prepared input contains a heading, generic skill statement or insufficient publication identifier. Manual input review is required; no search can reliably identify a work.'
            audit['input_quality_issue'] = 'non_factual_or_incomplete_publication'
            return r
        for provider, name in ((crossref, 'Crossref'), (pubmed, 'PubMed')):
            try:
                records = provider.lookup(self.client, audit, doi=doi, title=title)
                for m in records:
                    if self.compare_publication(claim, r, audit, m, name):
                        return r
            except FetchError as exc:
                audit['provider_failures'] = audit.get('provider_failures', []) + [dict(provider=name, reason=str(exc))]
        # A DOI registered outside Crossref is checked through DataCite before broad search.
        if doi:
            try:
                url = 'https://api.datacite.org/dois/' + quote(doi, safe='')
                d = self.client.json(url, audit, 'DataCite DOI exact match', doi)['data']['attributes']
                if d.get('doi', '').casefold() == doi.casefold():
                    matched = ['doi']
                    if str(claim.get('year', '')) == str(d.get('publicationYear')):
                        matched.append('year')
                    apply(r, evidence('DataCite', 'structured_DOI_metadata', url, 'A', matched,
                                      notes='DOI resource record found. Resource type may be code, dataset or preprint; not proof of a journal publication.'))
                    r['verification_status'] = Status.PARTIALLY_VERIFIED.value
                    r['verification_notes'] = 'DOI resolves to a DataCite resource; journal publication and supplied title require review.'
                    return r
            except (FetchError, KeyError, TypeError):
                pass
        query = '"' + (doi or title) + '"'
        try:
            leads = web.search(self.client, audit, query)
            # Two original publisher pages at most, never verify from search snippets.
            for lead in [x for x in leads if web.official_publisher(x['url'])][:2]:
                try:
                    meta, _ = web.inspect(self.client, audit, lead['url'])
                    m = web.citation_metadata(meta, lead['url'])
                    if m and self.compare_publication(claim, r, audit, m, 'Official publisher'):
                        return r
                except FetchError:
                    continue
        except FetchError:
            pass
        if audit.get('provider_failures') or len(title.split()) < 8 or not title[:1].isupper():
            r['verification_status'] = Status.NEEDS_REVIEW.value
            r['verification_notes'] = 'No reliable linkage was established; input may be truncated or sources unavailable. Manual review is required; absence is not falsehood.'
        else:
            r['verification_status'] = Status.NOT_FOUND.value
            r['verification_notes'] = 'Crossref, PubMed and bounded public web discovery did not yield a matching primary work record. NOT_FOUND is not FALSE; incomplete citations or network visibility may explain the result.'
        return r

    def patent(self, claim, r, audit):
        number = claim.get('patent_number', '').strip()
        if not number:
            r['verification_notes'] = 'No patent number or structured patent title supplied. Manual input review required; no invention or ownership inferred.'
            audit['input_quality_issue'] = 'missing_patent_identifier'
            return r
        # Official sources first; discovery alone does not establish a patent record.
        for domain in ('patentscope.wipo.int', 'worldwide.espacenet.com'):
            try:
                web.search(self.client, audit, '"' + number + '" site:' + domain)
            except FetchError:
                continue
        url = 'https://patents.google.com/patent/' + quote(number, safe='') + '/en'
        try:
            meta, text = web.inspect(self.client, audit, url)
            record_number = meta.get('dc.relation', []) + meta.get('citation_pdf_url', [])
            if norm(number) not in norm(text) and not any(norm(number) in norm(v) for v in record_number):
                raise FetchError('Patent record number not matched')
            title = next(iter(meta.get('dc.title', [])), '')
            apply(r, evidence('Google Patents', 'patent_metadata_index', url, 'C', ['patent_number'],
                              notes='Public patent metadata index matches number. Inventors, applicant, year and current legal status not established from supplied fields.'))
            r['evidence'][-1]['verified_metadata'] = dict(patent_number=number, title=title)
            r['verification_status'] = Status.PARTIALLY_VERIFIED.value
            r['verification_notes'] = 'Patent number located in an authoritative public patent index. The supplied claim does not establish inventorship, applicant or legal status; primary registry/manual review recommended.'
        except FetchError:
            r['verification_status'] = Status.NEEDS_REVIEW.value
            r['verification_notes'] = 'Official patent discovery and a public patent index did not yield accessible matching metadata. Number may be an application identifier or source may be unavailable; no adverse inference.'
        return r

    def event(self, claim, r, audit):
        name = safe_text(claim.get('award_name') or claim.get('title') or '')
        if not name:
            # Only an explicitly quoted public title is usable from unstructured text.
            quoted = re.search(r'[“"]([^”"]{12,180})[”"]', claim.get('claim_text', ''))
            if quoted:
                name = safe_text(quoted.group(1))
        if not name or HEADINGS.fullmatch(name) or len(name) > 180 or re.search(r'presented annually|top \d|获得证书|熟练|研究生.*奖学金', name, re.I):
            r['verification_notes'] = 'Prepared claim lacks a specific public event/award title with recipient/presentation linkage. Heading, descriptive sentence or local honour cannot safely identify an individual result.'
            audit['input_quality_issue'] = 'missing_event_or_recipient_linkage'
            return r
        query = '"' + name + '"'
        if claim.get('year'):
            query += ' ' + claim['year']
        if claim.get('organization'):
            query += ' ' + safe_text(claim['organization'])[:80]
        try:
            leads = web.search(self.client, audit, query)
            for lead in leads[:2]:
                # Inspect source existence only. No name search or identity reconstruction.
                try:
                    web.inspect(self.client, audit, lead['url'])
                    audit['sources_rejected'].append(dict(url=lead['url'], rejection_reason='Event/award existence cannot link the anonymous claim to recipient or presentation'))
                except FetchError:
                    continue
        except FetchError:
            pass
        r['verification_notes'] = 'Bounded public source search cannot link the supplied anonymous claim to an individual award, rank or presentation. Event existence alone is insufficient. Review programme/winner record or supporting document.'
        return r
