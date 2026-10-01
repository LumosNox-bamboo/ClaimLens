'use strict';
const byId = id => document.getElementById(id);
const payload = byId('report-data');
const cell = value => { const td = document.createElement('td'); td.textContent = value ?? ''; return td; };
function reportLink(cid, label, anonymous=false, claimId='') {
  const a = document.createElement('a');
  a.href = `${anonymous ? 'anonymous' : 'named'}/${encodeURIComponent(cid)}.html${claimId ? '#' + encodeURIComponent(claimId) : ''}`;
  a.textContent = label;
  return a;
}
if (payload) {
  const data = JSON.parse(payload.textContent);
  const matches = c => {
    const query = byId('search').value.trim().toLocaleLowerCase();
    if (![c.candidate_name, c.application_id, c.candidate_id].join(' ').toLocaleLowerCase().includes(query)) return false;
    const filter = byId('candidate-filter').value;
    if (filter === 'all') return true;
    if (filter === 'queue') return c.high_value_review_count > 0;
    if (filter === 'CV_UPDATE_AVAILABLE') return c.cv_updates > 0;
    if (filter in c.status_counts) return c.status_counts[filter] > 0;
    return c.claim_type_counts[filter] > 0;
  };
  function renderCandidates() {
    const sort = byId('candidate-sort').value;
    const rows = data.candidates.filter(matches).sort((a,b) => {
      const key = {claims:'claims_total',review:'needs_review',evidence:'public_evidence_claims',updates:'cv_updates'}[sort];
      if (key) {
        const diff = sort === 'review' ? b.status_counts.NEEDS_REVIEW-a.status_counts.NEEDS_REVIEW : b[key]-a[key];
        if (diff) return diff;
      }
      const text = sort === 'name' ? 'candidate_name' : 'application_id';
      return (a[text] || '').localeCompare(b[text] || '') || a.candidate_id.localeCompare(b.candidate_id);
    });
    const body = byId('candidate-rows'); body.replaceChildren();
    for (const c of rows) {
      const tr = document.createElement('tr'); const s = c.status_counts, t = c.claim_type_counts;
      if (s.CONFLICT) tr.className = 'conflict-row';
      for (const v of [c.application_id,c.candidate_name || 'Mapping unavailable',c.candidate_id,t.publication,t.award+t.competition,t.patent,t.conference_presentation,s.VERIFIED,s.PARTIALLY_VERIFIED,s.NOT_FOUND,s.NEEDS_REVIEW]) tr.append(cell(v));
      const update = cell(c.cv_updates ? `${c.cv_updates} · Update available` : '0'); if(c.cv_updates) update.className='update-text';tr.append(update);
      const view = cell(''); view.append(reportLink(c.candidate_id,'View'),document.createTextNode(' · '),reportLink(c.candidate_id,'Anonymous',true));tr.append(view);
      body.append(tr);
    }
    byId('visible-count').textContent = `${rows.length} of ${data.candidates.length} candidates`;
  }
  function renderQueue() {
    const category = byId('queue-category').value;
    const rows = data.queue.filter(r => category === 'all' || r.review_category === category);
    const body = byId('queue-rows');body.replaceChildren();
    for(const r of rows) {
      const tr = document.createElement('tr');if(r.status==='CONFLICT')tr.className='conflict-row';
      tr.append(cell(r.application_id),cell(`${r.claim_type}: ${r.title}`),cell(r.status),cell(`${r.review_category}: ${r.review_reason}`));
      const view = cell(''); view.append(reportLink(r.candidate_id,'View claim',false,r.claim_id));tr.append(view);body.append(tr);
    }
    byId('queue-count').textContent=`${rows.length} claims`;
  }
  for (const id of ['search','candidate-filter','candidate-sort']) byId(id).addEventListener(id==='search'?'input':'change',renderCandidates);
  for (const button of document.querySelectorAll('[data-filter]')) button.addEventListener('click',()=> {byId('candidate-filter').value=button.dataset.filter;renderCandidates();byId('search').scrollIntoView({block:'center'});});
  byId('queue-category').addEventListener('change',renderQueue);
  renderCandidates();renderQueue();
}
const claimFilter=byId('claim-filter');
if(claimFilter) claimFilter.addEventListener('change',()=>{
  for(const card of document.querySelectorAll('.claim')) card.hidden=claimFilter.value==='review' ? !['CONFLICT','PARTIALLY_VERIFIED','NEEDS_REVIEW','NOT_FOUND'].includes(card.dataset.status) : claimFilter.value!=='all' && card.dataset.status!==claimFilter.value;
});
if(location.hash) {
  const target=byId(decodeURIComponent(location.hash.slice(1)));
  if(target) { for(let p=target.parentElement;p;p=p.parentElement) if(p.tagName==='DETAILS')p.open=true;target.scrollIntoView({block:'start'}); }
}
