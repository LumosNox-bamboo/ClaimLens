"""JIF is independent of factual verification; never derived from another metric."""
import re
import threading
from datetime import datetime, timezone

from .models import empty_metrics
from .providers.http import FetchError
from .providers.web import inspect, official_publisher, search


def extract_jif(text, year):
    # Explicitly remove five-year labels before reading the two-year JIF.
    text = re.sub(r'5[- ]year\s+(?:Journal\s+)?Impact\s+Factor\s*[:=]?\s*\d+(?:\.\d+)?\s*(?:\(\d{4}\))?', '', text, flags=re.I)
    patterns = [
        rf'{year}\s*(?:Journal\s+)?Impact\s+Factor\s*[:=\-]?\s*(\d+(?:\.\d+)?)',
        rf'(\d+(?:\.\d+)?)\s*(?:Journal\s+)?Impact\s+Factor\s*\({year}\)',
        rf'(?:Journal\s+)?Impact\s+Factor\s*[:=]?\s*(\d+(?:\.\d+)?)\s*\({year}\)',
    ]
    values = {float(m.group(1)) for pattern in patterns for m in re.finditer(pattern, text, re.I)}
    return values.pop() if len(values) == 1 else None


class Metrics:
    def __init__(self, client):
        self.client = client
        self.cache = {}
        self.lock = threading.Lock()

    def lookup(self, journal, audit):
        if not journal:
            audit['metric_notes'] = 'No reliably identified journal; JIF unavailable.'
            return empty_metrics()
        # Journals share lookup results, not candidate information.
        with self.lock:
            if journal in self.cache:
                value, queries, sources, rejected = self.cache[journal]
                audit['metric_search_queries'] = queries
                audit['metric_sources_considered'] = sources
                audit['metric_sources_rejected'] = rejected
                audit['metric_notes'] = 'Cached journal-level lookup.'
                return dict(value)
            target_year = datetime.now(timezone.utc).year - 1
            ma = dict(search_queries=[], sources_considered=[], sources_rejected=[], search_attempt_count=0)
            metric = empty_metrics()
            try:
                leads = search(self.client, ma, '"' + journal + '" ' + str(target_year) + ' "Journal Impact Factor"')
                for lead in [x for x in leads if official_publisher(x['url'])][:3]:
                    try:
                        _, text = inspect(self.client, ma, lead['url'])
                        # Year and metric must form one explicit label. No search snippet extraction.
                        value = extract_jif(text, target_year)
                        if value is not None and journal.casefold() in text.casefold():
                            metric.update(latest_jif=value, jif_year=target_year,
                                          metric_source='Official journal/publisher page', metric_source_url=lead['url'],
                                          metric_source_quality='official_publisher')
                            break
                        ma['sources_rejected'].append(dict(url=lead['url'], rejection_reason='No unambiguous latest-year JIF label for this journal'))
                    except FetchError:
                        continue
            except FetchError:
                pass
            self.cache[journal] = (metric, ma['search_queries'], ma['sources_considered'], ma['sources_rejected'])
            audit['metric_search_queries'] = ma['search_queries']
            audit['metric_sources_considered'] = ma['sources_considered']
            audit['metric_sources_rejected'] = ma['sources_rejected']
            audit['metric_notes'] = 'Latest-year JIF found.' if metric['latest_jif'] is not None else 'No reliably accessible, explicitly dated latest JIF; null does not affect verification.'
            return dict(metric)
