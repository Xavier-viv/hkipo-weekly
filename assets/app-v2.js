const $ = id => document.getElementById(id);
const pct = (v,d=1) => v == null ? '—' : `${v>=0?'+':''}${(v*100).toFixed(d)}%`;
const money = v => v == null ? '—' : `HK$${Number(v).toLocaleString('zh-CN',{maximumFractionDigits:1})}亿`;
const turnoverMoney = v => v == null ? '—' : `HK$${Math.round(v/1e8).toLocaleString('zh-CN')}亿`;const shortDate = v => v ? v.slice(5).replace('-','.') : '—';
const period = (a,b) => `${shortDate(a)}—${shortDate(b)}`;
const safe = v => String(v??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const industry = v => `<span class="industry-tag">${safe(v||'其他')}</span>`;

function renderEvents(target, items) {
  target.innerHTML = items.length ? items.map(item => `<span class="event-tag"><b>${safe(item.company)}</b>${industry(item.industry)}<small>${shortDate(item.date)} · ${safe(item.board)}</small></span>`).join('') : '<span class="empty-tag">本周暂无新增</span>';
}

function render(report) {
  const {meta,issuance,hkex,csrc}=report;
  $('report-period').textContent=period(meta.weekStart,meta.weekEnd);
  $('as-of').textContent=`数据截至 ${meta.asOf}`;
  $('weekly-totals').innerHTML=`<span>本周<strong>${issuance.weekly.count}</strong>上市</span><span><strong>${hkex.weeklyPhips.length}</strong>通过聆讯</span><span><strong>${hkex.weeklyApplicationProofs.length}</strong>申请版本</span>`;
  $('weekly-listing-count').textContent=`${issuance.weekly.count}家`;
  $('weekly-listings').innerHTML=issuance.weekly.companies.length?issuance.weekly.companies.map(item=>`<tr>
    <td data-label="公司"><strong>${safe(item.shortName||item.name)}</strong><small class="company-full-name">${safe(item.name)} · ${item.code}</small></td>
    <td data-label="行业">${industry(item.industry)}</td>
    <td data-label="上市日">${item.listedOn}</td><td data-label="发行价">HK$${item.offerPrice.toFixed(2)}</td><td data-label="发行市盈率">${safe(item.issuePeDisplay||'待核验')}</td><td data-label="募资额">${money(item.fundraisingHkd100m)}</td>
    <td data-label="首日收市">HK$${item.firstDayClose.toFixed(2)}</td><td data-label="首日涨跌" class="${item.firstDayReturn>=0?'positive':'negative'}">${pct(item.firstDayReturn)}</td>
    <td data-label="保荐人" class="sponsor-cell">${safe(item.sponsors||'—')}</td></tr>`).join(''):'<tr><td colspan="9">本周无新上市公司</td></tr>';
  $('annual-funds').textContent=money(issuance.annual.fundraisingHkd100m);
  $('annual-count').textContent=`${issuance.annual.count}家`;
  $('return-universe').textContent=`${issuance.annual.returnUniverse}家`;
  $('market-date').textContent=`收市价截至 ${meta.marketDataAsOf}`;
  $('top-performers').innerHTML=issuance.annual.topPerformers.map(item=>`<li><span><b>${safe(item.shortName||item.name)}</b>${industry(item.industry)}</span><strong>${pct(item.latestReturn)}</strong></li>`).join('');

  const workload=hkex.officialWorkload;
  $('workload-as-of').textContent=`截至 ${workload.asOf}`;
  $('active-total').textContent=workload.underProcessing;$('public-visible').textContent=`${hkex.activeCount}宗`;$('ytd-processed').textContent=`${workload.processed}宗`;$('approved-pending').textContent=`${workload.approvedPending}宗`;
  $('phip-count').textContent=hkex.weeklyPhips.length;$('a1-count').textContent=hkex.weeklyApplicationProofs.length;
  renderEvents($('phip-list'),hkex.weeklyPhips);renderEvents($('a1-list'),hkex.weeklyApplicationProofs);

  const statuses=csrc.statusCounts||{};$('csrc-total').textContent=`${csrc.recordCount}项`;$('csrc-accepted').textContent=`${statuses['已接收']||0}项`;$('csrc-consulting').textContent=`${statuses['征求意见']||0}项`;$('csrc-supplement').textContent=`${statuses['补充材料']||0}项`;
  const max=Math.max(1,...Object.values(statuses));$('status-bars').innerHTML=Object.entries(statuses).sort((a,b)=>b[1]-a[1]).map(([label,count])=>`<div class="status-row"><span>${safe(label)}</span><div class="status-track"><i style="width:${count/max*100}%"></i></div><b>${count}项</b></div>`).join('');
  $('received-count').textContent=`${csrc.weeklyNewReceived.length}项`;$('received-list').innerHTML=csrc.weeklyNewReceived.length?csrc.weeklyNewReceived.map(item=>`<div class="received-item"><strong>${safe(item.company)}</strong><div>${industry(item.industry)}<span>${item.receivedOn}</span></div></div>`).join(''):'<div class="received-item"><strong>本周暂无新增已接收</strong></div>';

  const decision=report.decision,congestion=decision.congestion,market=decision.market,valuation=decision.valuation,sentiment=decision.sentiment;
  $('window-summary').textContent=decision.windowSummary;$('window-as-of').textContent=`截至 ${market.asOf}`;
  $('congestion-label').textContent=congestion.label;$('congestion-active').textContent=`${congestion.underProcessing}宗`;$('congestion-a1').textContent=`${congestion.publicVisible}家`;$('congestion-phip').textContent=`${congestion.newApplicationToListingRatio.toFixed(1)}x`;$('congestion-listings').textContent=`${congestion.medianApplicationToHearingBundleDays}天`;
  $('market-label').textContent=market.label;$('hsi-return').textContent=`恒指 ${pct(market.hsiWeeklyReturn)}`;$('hscei-return').textContent=pct(market.hsceiWeeklyReturn);$('market-turnover').textContent=turnoverMoney(market.turnoverHkd);$('turnover-change').textContent=pct(market.turnoverWeeklyChange);
  $('consumer-pe').textContent=`可选消费 ${valuation.consumerDiscretionaryPe.toFixed(1)}x`;$('hsi-pe').textContent=`${valuation.hsiPe.toFixed(1)}x`;$('hstech-pe').textContent=`${valuation.hstechPe.toFixed(1)}x`;$('consumer-return').textContent=pct(valuation.consumerDiscretionaryOneMonthReturn);$('valuation-date').textContent=`估值数据截至 ${valuation.asOf}`;
  $('sentiment-label').textContent=sentiment.label;$('ipo-median').textContent=`新股中位数 ${pct(sentiment.weeklyIpoMedianReturn)}`;$('ipo-positive').textContent=sentiment.weeklyIpoCount?`${Math.round(sentiment.weeklyIpoPositiveRatio*sentiment.weeklyIpoCount)}/${sentiment.weeklyIpoCount}`:'—';$('market-breadth').textContent=`${market.advances.toLocaleString('zh-CN')} / ${market.declines.toLocaleString('zh-CN')}`;$('breadth-ratio').textContent=market.advanceDeclineRatio?.toFixed(2)??'—';}

fetch(`data/report.json?v=${Date.now()}`)
  .then(response=>{if(!response.ok)throw new Error(`数据文件 HTTP ${response.status}`);return response.json();})
  .then(render)
  .catch(error=>{document.body.innerHTML=`<main class="load-error"><h1>数据加载失败</h1><p>${safe(error.message)}</p></main>`;});
