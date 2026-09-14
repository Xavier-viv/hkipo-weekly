const palette = {
  ruby: '#8b1a2b', red: '#c41230', burgundy: '#590d1a', cream: '#fff7e9',
  creamDeep: '#f3ddbd', ivory: '#f5f2ef', ink: '#182235', muted: '#687487',
  line: '#e4e7ec', blue: '#405a7a', green: '#078f6b', white: '#ffffff'
};

let report;

const $ = (id) => document.getElementById(id);
const pct = (value, digits = 1) => value == null ? '—' : `${value >= 0 ? '+' : ''}${(value * 100).toFixed(digits)}%`;
const money = (value) => value == null ? '—' : `HK$${Number(value).toLocaleString('zh-CN', {maximumFractionDigits: 1})}亿`;
const shortDate = (value) => value ? value.slice(5).replace('-', '.') : '—';
const period = (a, b) => `${shortDate(a)}—${shortDate(b)}`;
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const currentSiteUrl = () => location.protocol === 'http:' || location.protocol === 'https:' ? location.href.split(/[?#]/)[0] : '';

function renderTagList(target, items) {
  target.innerHTML = items.length ? items.map(item => `<a href="${escapeHtml(item.document)}" target="_blank" rel="noopener">${escapeHtml(item.company)} · ${shortDate(item.date)}</a>`).join('') : '<span>本周暂无新增</span>';
}

function render() {
  const meta = report.meta;
  const weekly = report.issuance.weekly;
  const annual = report.issuance.annual;
  $('report-period').textContent = period(meta.weekStart, meta.weekEnd);
  $('as-of').textContent = `数据截至 ${meta.asOf}`;
  $('weekly-totals').innerHTML = `<span>本周 <strong>${weekly.count}</strong> 上市</span><span><strong>${report.hkex.weeklyPhips.length}</strong> 聆讯后资料集</span><span><strong>${report.hkex.weeklyApplicationProofs.length}</strong> 申请版本</span><span><strong>${report.csrc.weeklyNewReceived.length}</strong> 备案材料接收</span>`;
  $('weekly-listing-count').textContent = `${weekly.count}家`;
  $('weekly-listings').innerHTML = weekly.companies.length ? weekly.companies.map(item => `<tr>
    <td>${escapeHtml(item.name)}<div class="muted">${item.code}</div></td>
    <td>${item.listedOn}</td><td>HK$${item.offerPrice.toFixed(2)}</td><td>${money(item.fundraisingHkd100m)}</td>
    <td>HK$${item.firstDayClose.toFixed(2)}</td><td class="${item.firstDayReturn >= 0 ? 'positive' : 'negative'}">${pct(item.firstDayReturn)}</td>
    <td title="${escapeHtml(item.sponsors)}">${escapeHtml(item.sponsors || '—')}</td></tr>`).join('') : '<tr><td colspan="7">本周无新上市公司</td></tr>';
  $('annual-funds').textContent = money(annual.fundraisingHkd100m);
  $('annual-count').textContent = `${annual.count}家`;
  $('return-universe').textContent = `${annual.returnUniverse}家`;
  $('market-date').textContent = `收市价截至 ${meta.marketDataAsOf}`;
  $('top-performers').innerHTML = annual.topPerformers.map(item => `<li><span>${escapeHtml(item.name)}</span><b>${pct(item.latestReturn)}</b></li>`).join('');

  const hkex = report.hkex;
  $('active-total').textContent = hkex.activeCount;
  $('main-count').textContent = `${hkex.mainBoardCount}家`;
  $('gem-count').textContent = `${hkex.gemCount}家`;
  const mainRate = hkex.activeCount ? hkex.mainBoardCount / hkex.activeCount * 100 : 0;
  $('pipeline-donut').style.background = `conic-gradient(${palette.blue} 0 ${mainRate}%, ${palette.red} ${mainRate}% 100%)`;
  $('phip-count').textContent = hkex.weeklyPhips.length;
  $('a1-count').textContent = hkex.weeklyApplicationProofs.length;
  renderTagList($('phip-list'), hkex.weeklyPhips);
  renderTagList($('a1-list'), hkex.weeklyApplicationProofs);

  const csrc = report.csrc;
  const statuses = csrc.statusCounts || {};
  $('csrc-total').textContent = `${csrc.recordCount}家`;
  $('csrc-accepted').textContent = `${statuses['已接收'] || 0}家`;
  $('csrc-consulting').textContent = `${statuses['征求意见'] || 0}家`;
  $('csrc-supplement').textContent = `${statuses['补充材料'] || 0}家`;
  const maxStatus = Math.max(1, ...Object.values(statuses));
  $('status-bars').innerHTML = Object.entries(statuses).sort((a,b) => b[1]-a[1]).map(([label, count]) => `<div class="status-row"><span>${escapeHtml(label)}</span><div class="status-track"><i style="width:${count/maxStatus*100}%"></i></div><b>${count}家</b></div>`).join('');
  $('received-count').textContent = `${csrc.weeklyNewReceived.length}家`;
  $('received-list').innerHTML = csrc.weeklyNewReceived.length ? csrc.weeklyNewReceived.map(item => `<div class="received-item"><strong>${escapeHtml(item.company)}</strong><span>${item.receivedOn}</span></div>`).join('') : '<div class="received-item"><strong>本周暂无新增接收</strong></div>';

  $('source-list').innerHTML = report.sources.map(item => `<a class="source-item" href="${escapeHtml(item.url)}" target="_blank" rel="noopener"><div><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(item.usedFor)}</span></div><em>${escapeHtml(item.asOf || '')}</em></a>`).join('');
}

function renderQr() {
  const target = $('site-qr');
  const url = currentSiteUrl();
  target.innerHTML = '';
  if (!url) {
    target.textContent = '部署后生成';
    $('qr-note').textContent = '通过 HTTP 预览或部署后自动指向本站';
    return;
  }
  new QRCode(target, {text: url, width: 116, height: 116, colorDark: palette.ink, colorLight: '#ffffff', correctLevel: QRCode.CorrectLevel.M});
}

function roundedRect(ctx, x, y, w, h, r, fill, stroke) {
  ctx.beginPath(); ctx.roundRect(x,y,w,h,r); ctx.fillStyle = fill; ctx.fill();
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
}
function canvasText(ctx, text, x, y, size, color=palette.ink, weight=500, align='left') {
  ctx.font = `${weight} ${size}px "Microsoft YaHei","PingFang SC",sans-serif`; ctx.fillStyle = color; ctx.textAlign = align; ctx.fillText(String(text), x, y);
}
function wrapText(ctx, text, x, y, maxWidth, lineHeight, maxLines=3) {
  const chars = Array.from(String(text)); let line=''; let lines=[];
  for (const ch of chars) { const test=line+ch; if (ctx.measureText(test).width>maxWidth && line) { lines.push(line); line=ch; } else line=test; }
  if (line) lines.push(line); lines.slice(0,maxLines).forEach((v,i)=>ctx.fillText(v,x,y+i*lineHeight));
}

function drawPoster() {
  const c = $('poster-canvas'); const ctx = c.getContext('2d'); const w=c.width;
  ctx.clearRect(0,0,w,c.height); ctx.fillStyle=palette.ivory; ctx.fillRect(0,0,w,c.height);
  const grad=ctx.createLinearGradient(0,0,w,520); grad.addColorStop(0,palette.burgundy); grad.addColorStop(.55,palette.ruby); grad.addColorStop(1,palette.red); ctx.fillStyle=grad; ctx.fillRect(0,0,w,520);
  ctx.strokeStyle='rgba(255,255,255,.12)'; ctx.lineWidth=2; ctx.beginPath(); ctx.arc(1010,30,260,0,Math.PI*2); ctx.stroke();
  canvasText(ctx,'HONG KONG IPO MARKET',68,62,18,palette.white,800); canvasText(ctx,'港股市场',68,148,64,palette.white,850);
  const titleGrad=ctx.createLinearGradient(50,0,760,0); titleGrad.addColorStop(0,palette.cream); titleGrad.addColorStop(1,palette.creamDeep); roundedRect(ctx,48,178,720,114,0,titleGrad); canvasText(ctx,'审核动态周报',72,266,88,'#711322',900);
  canvasText(ctx,period(report.meta.weekStart,report.meta.weekEnd),68,346,38,palette.white,850); canvasText(ctx,`数据截至 ${report.meta.asOf}`,300,345,20,'#efd6db',600);
  ctx.strokeStyle='rgba(255,255,255,.32)'; ctx.beginPath();ctx.moveTo(68,382);ctx.lineTo(1012,382);ctx.stroke();
  canvasText(ctx,`本周 ${report.issuance.weekly.count} 上市   ${report.hkex.weeklyPhips.length} 聆讯后资料集   ${report.hkex.weeklyApplicationProofs.length} 申请版本   ${report.csrc.weeklyNewReceived.length} 材料接收`,68,440,24,palette.white,800);
  const qrCanvas=$('site-qr').querySelector('canvas'); if(qrCanvas){roundedRect(ctx,862,390,140,110,14,palette.cream);roundedRect(ctx,870,398,124,94,10,palette.white);ctx.drawImage(qrCanvas,884,401,96,96);}

  let y=570;
  const sectionTitle=(index,title,subtitle)=>{roundedRect(ctx,58,y,66,66,17,palette.ruby);canvasText(ctx,index,91,y+43,22,palette.white,850,'center');canvasText(ctx,title,146,y+37,38,palette.ink,850);canvasText(ctx,subtitle,146,y+65,17,palette.muted,600);y+=105;};
  sectionTitle('01','发行上市情况','港交所官方发行和行情数据');
  roundedRect(ctx,58,y,964,240,24,palette.white,palette.line); canvasText(ctx,'本周新上市',84,y+39,20,palette.ruby,800); canvasText(ctx,`${report.issuance.weekly.count}家`,988,y+39,18,palette.ruby,850,'right');
  const heads=['公司','募资额','首日涨跌','保荐人']; [84,430,620,760].forEach((x,i)=>canvasText(ctx,heads[i],x,y+72,13,palette.muted,700));
  report.issuance.weekly.companies.forEach((item,i)=>{const yy=y+112+i*50;if(i%2===0)roundedRect(ctx,72,yy-28,936,42,10,'#fffbfb');canvasText(ctx,item.name,84,yy,15,palette.ink,750);canvasText(ctx,money(item.fundraisingHkd100m),430,yy,15,palette.ink,700);canvasText(ctx,pct(item.firstDayReturn),620,yy,16,item.firstDayReturn>=0?palette.red:palette.green,850);ctx.font=`600 13px "Microsoft YaHei"`;ctx.fillStyle=palette.muted;wrapText(ctx,item.sponsors||'—',760,yy,225,16,1);});
  y+=270;
  roundedRect(ctx,58,y,964,190,24,palette.white,palette.line); canvasText(ctx,'年内概览',84,y+38,20,palette.ruby,800); roundedRect(ctx,84,y+60,278,104,16,palette.ruby);canvasText(ctx,'累计募资',106,y+91,15,'#f0c9cf',650);canvasText(ctx,money(report.issuance.annual.fundraisingHkd100m),106,y+137,28,palette.white,900);
  roundedRect(ctx,382,y+60,220,104,16,'#fafbfc',palette.line);canvasText(ctx,'IPO / 介绍上市',404,y+91,14,palette.muted,650);canvasText(ctx,`${report.issuance.annual.count}家`,404,y+137,30,palette.ruby,900);
  roundedRect(ctx,622,y+60,376,104,16,'#fafbfc',palette.line);canvasText(ctx,'年内涨幅前五',644,y+89,14,palette.muted,700);report.issuance.annual.topPerformers.slice(0,5).forEach((v,i)=>{canvasText(ctx,`${i+1}  ${v.name}`,644,y+113+i*15,11,palette.ink,650);canvasText(ctx,pct(v.latestReturn),980,y+113+i*15,11,palette.ruby,800,'right');});
  y+=240;
  sectionTitle('02','联交所审核动态','有效申请及本周文件节点');
  roundedRect(ctx,58,y,450,350,24,palette.white,palette.line);canvasText(ctx,'有效申请',84,y+40,18,palette.ruby,800);canvasText(ctx,String(report.hkex.activeCount),280,y+175,58,palette.blue,900,'center');canvasText(ctx,'家',280,y+205,18,palette.muted,700,'center');canvasText(ctx,`主板 ${report.hkex.mainBoardCount}家`,110,y+290,18,palette.blue,800);canvasText(ctx,`GEM ${report.hkex.gemCount}家`,318,y+290,18,palette.red,800);
  roundedRect(ctx,530,y,492,160,24,palette.white,palette.line);canvasText(ctx,String(report.hkex.weeklyPhips.length),562,y+92,50,palette.ruby,900);canvasText(ctx,'本周聆讯后资料集',636,y+52,19,palette.ruby,800);ctx.font=`650 15px "Microsoft YaHei"`;ctx.fillStyle=palette.ink;wrapText(ctx,report.hkex.weeklyPhips.map(v=>v.company).join(' · ')||'暂无',636,y+85,340,23,3);
  roundedRect(ctx,530,y+180,492,170,24,palette.white,palette.line);canvasText(ctx,String(report.hkex.weeklyApplicationProofs.length),562,y+276,50,palette.ruby,900);canvasText(ctx,'本周申请版本',636,y+232,19,palette.ruby,800);ctx.font=`650 15px "Microsoft YaHei"`;ctx.fillStyle=palette.ink;wrapText(ctx,report.hkex.weeklyApplicationProofs.map(v=>v.company).join(' · ')||'暂无',636,y+265,340,23,3);
  y+=410;
  sectionTitle('03','中国证监会备案进度','最新备案情况表时点数据');
  const stats=[['在表项目',report.csrc.recordCount],['已接收',report.csrc.statusCounts['已接收']||0],['征求意见',report.csrc.statusCounts['征求意见']||0],['补充材料',report.csrc.statusCounts['补充材料']||0]];stats.forEach((s,i)=>{const x=58+i*241;roundedRect(ctx,x,y,224,104,17,palette.ruby);canvasText(ctx,s[0],x+18,y+35,14,'#f2cbd1',650);canvasText(ctx,`${s[1]}家`,x+18,y+80,30,palette.white,900);});
  y+=134;roundedRect(ctx,58,y,500,430,24,palette.white,palette.line);canvasText(ctx,'当前状态分布',84,y+42,20,palette.ruby,800);const statusEntries=Object.entries(report.csrc.statusCounts);const max=Math.max(...statusEntries.map(v=>v[1]),1);statusEntries.forEach(([label,count],i)=>{const yy=y+105+i*76;canvasText(ctx,label,84,yy,16,palette.ink,700);roundedRect(ctx,190,yy-19,280,24,12,'#f0e5e7');roundedRect(ctx,190,yy-19,280*count/max,24,12,palette.ruby);canvasText(ctx,`${count}家`,526,yy,16,palette.ruby,850,'right');});
  roundedRect(ctx,580,y,442,430,24,palette.white,palette.line);canvasText(ctx,'本周新增接收',606,y+42,20,palette.ruby,800);canvasText(ctx,`${report.csrc.weeklyNewReceived.length}家`,996,y+42,17,palette.ruby,850,'right');report.csrc.weeklyNewReceived.slice(0,11).forEach((v,i)=>{canvasText(ctx,v.company,606,y+88+i*30,14,palette.ink,700);canvasText(ctx,v.receivedOn,994,y+88+i*30,12,palette.muted,650,'right');});
  y+=485;sectionTitle('04','严格数据来源','仅使用港交所、中国证监会官方数据');
  report.sources.slice(0,8).forEach((s,i)=>{roundedRect(ctx,58,y+i*62,964,48,12,palette.white,palette.line);canvasText(ctx,s.label,78,y+30+i*62,14,palette.ink,750);canvasText(ctx,s.asOf||'',998,y+30+i*62,12,palette.muted,650,'right');});
  ctx.fillStyle=palette.ink;ctx.fillRect(0,3290,1080,110);canvasText(ctx,'港股市场审核动态周报 · VIVAIA THEME',58,3333,15,palette.white,800);canvasText(ctx,'仅供信息参考，不构成投资建议',58,3365,12,'#aab4c5',550);canvasText(ctx,report.meta.asOf,1020,3365,12,'#aab4c5',650,'right');
}

function openPoster() { drawPoster(); $('poster-modal').hidden=false; document.body.style.overflow='hidden'; }
function closePoster() { $('poster-modal').hidden=true; document.body.style.overflow=''; }
function savePoster() { drawPoster(); $('poster-canvas').toBlob(blob=>{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`港股市场审核动态周报_${report.meta.weekStart}_${report.meta.weekEnd}.png`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);},'image/png'); }

async function init() {
  try {
    const res = await fetch(`data/report.json?v=${Date.now()}`); if (!res.ok) throw new Error(`HTTP ${res.status}`); report=await res.json(); render(); renderQr();
    $('download-poster').addEventListener('click',openPoster); $('close-poster').addEventListener('click',closePoster); $('save-poster').addEventListener('click',savePoster); $('poster-modal').addEventListener('click',e=>{if(e.target===$('poster-modal'))closePoster();});
  } catch (error) {
    document.body.innerHTML=`<main style="max-width:760px;margin:80px auto;padding:30px;font-family:sans-serif"><h1 style="font-size:34px;clip-path:none">数据加载失败</h1><p>${escapeHtml(error.message)}</p><p>请先运行 scripts/fetch_data.py 生成 data/report.json。</p></main>`;
  }
}
init();

