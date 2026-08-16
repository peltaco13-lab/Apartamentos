const state={data:null,listings:[],filtered:[]};
const $=s=>document.querySelector(s);
const els={
  grid:$("#listingsGrid"),empty:$("#emptyState"),emptyClear:$("#emptyClear"),search:$("#searchInput"),
  area:$("#areaFilter"),zone:$("#zoneFilter"),source:$("#sourceFilter"),beds:$("#bedFilter"),sort:$("#sortFilter"),
  knownPrice:$("#knownPriceOnly"),clear:$("#clearFilters"),count:$("#resultCount"),status:$("#statusBox"),
  lastUpdated:$("#lastUpdated"),statTotal:$("#statTotal"),statMin:$("#statMin"),statZones:$("#statZones"),
  statUpdated:$("#statUpdated"),sourceLinks:$("#sourceLinks"),sourceSummary:$("#sourceSummary"),themeBtn:$("#themeBtn"),
  budgetInput:$("#budgetInput"),budgetRange:$("#budgetRange"),budgetUnlimited:$("#budgetUnlimited"),
  budgetDisplay:$("#budgetDisplay"),budgetRangeMax:$("#budgetRangeMax"),budgetCard:document.querySelector(".budget-card")
};
const money=new Intl.NumberFormat("es-CO",{style:"currency",currency:"COP",maximumFractionDigits:0});

function escapeHtml(v=""){return String(v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;")}
function safeHttpUrl(v){try{const u=new URL(v);return["http:","https:"].includes(u.protocol)?u.href:"#"}catch{return"#"}}
function formatPrice(p){return Number.isFinite(p)?money.format(p):"Precio por revisar"}
function parseDate(v){const d=new Date(v);return Number.isNaN(d.getTime())?null:d}
function shortDate(v){const d=parseDate(v);if(!d)return"fecha no disponible";return new Intl.DateTimeFormat("es-CO",{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}).format(d)}
function relativeHours(v){const d=parseDate(v);if(!d)return"—";const h=Math.max(0,Math.round((Date.now()-d.getTime())/36e5));if(h<1)return"<1 h";if(h<24)return`${h} h`;return`${Math.round(h/24)} d`}

function compactMoney(value){
  if(!Number.isFinite(value)||value<=0)return"Sin límite";
  if(value>=1_000_000)return`$${new Intl.NumberFormat("es-CO",{maximumFractionDigits:1}).format(value/1_000_000)} M`;
  return money.format(value);
}
function currentBudget(){
  if(els.budgetUnlimited.checked)return null;
  const value=Number(els.budgetInput.value||els.budgetRange.value||0);
  return Number.isFinite(value)&&value>0?value:null;
}
function ensureRangeCovers(value){
  const currentMax=Number(els.budgetRange.max);
  if(value<=currentMax)return;
  const block=5_000_000;
  els.budgetRange.max=String(Math.ceil(value/block)*block);
}
function renderBudget(){
  const budget=currentBudget();
  els.budgetDisplay.textContent=budget?formatPrice(budget):"Sin límite";
  els.budgetRangeMax.textContent=`${compactMoney(Number(els.budgetRange.max))}+`;
  els.budgetCard.dataset.limited=budget?"true":"false";
}
function setBudget(value,{fromRange=false}={}){
  const numeric=Number(value||0);
  if(!Number.isFinite(numeric)||numeric<=0){
    els.budgetUnlimited.checked=true;
    els.budgetInput.value="";
  }else{
    els.budgetUnlimited.checked=false;
    ensureRangeCovers(numeric);
    if(!fromRange)els.budgetRange.value=String(numeric);
    els.budgetInput.value=String(Math.round(numeric));
  }
  renderBudget();
  applyFilters();
}

function fillSelect(select,values){
  const current=select.value;
  const options=[...new Set(values.filter(Boolean))].sort((a,b)=>a.localeCompare(b,"es"));
  select.querySelectorAll("option:not(:first-child)").forEach(n=>n.remove());
  options.forEach(value=>{const option=document.createElement("option");option.value=value;option.textContent=value;select.appendChild(option)});
  if(options.includes(current))select.value=current;
}

function specsHtml(item){
  const specs=[];
  if(item.bedrooms)specs.push(`<span>${escapeHtml(item.bedrooms)} hab.</span>`);
  if(item.bathrooms)specs.push(`<span>${escapeHtml(item.bathrooms)} baños</span>`);
  if(item.area_m2)specs.push(`<span>${escapeHtml(item.area_m2)} m²</span>`);
  if(item.parking)specs.push(`<span>${escapeHtml(item.parking)} parq.</span>`);
  if(!specs.length)specs.push("<span>Detalles en el aviso</span>");
  return specs.join("");
}

function listingSources(item){
  const names=Array.isArray(item.sources)&&item.sources.length?item.sources:[item.source].filter(Boolean);
  return [...new Set(names)];
}
function listingLinks(item){
  if(Array.isArray(item.links)&&item.links.length)return item.links;
  return item.url?[{source:item.source||"Web",url:item.url}]:[];
}
function sourceLinksHtml(item){
  const links=listingLinks(item).slice(0,3);
  if(links.length<=1)return"";
  return `<div class="card-source-links">${links.map(link=>`<a href="${escapeHtml(safeHttpUrl(link.url))}" target="_blank" rel="noopener noreferrer">${escapeHtml(link.source)} ↗</a>`).join("")}</div>`;
}
function cardHtml(item){
  const url=safeHttpUrl(item.url);
  const stale=item.stale?'<span class="stale-badge">por revisar</span>':"";
  const priceClass=Number.isFinite(item.price)?"":" price-unknown";
  const seen=item.last_seen?`Visto ${shortDate(item.last_seen)}`:"Visto recientemente";
  const sources=listingSources(item),sourceLabel=sources.length>1?`${sources[0]} +${sources.length-1}`:(sources[0]||"Web");
  const multi=sources.length>1?`<span class="multi-source">${sources.length} fuentes</span>`:"";
  return `<article class="listing-card">
    <div class="card-top"><span class="source-name">${escapeHtml(sourceLabel)}</span>${stale}</div>
    <strong class="card-price${priceClass}">${escapeHtml(formatPrice(item.price))}</strong>
    <h3 class="card-title">${escapeHtml(item.title||"Apartamento en arriendo")}</h3>
    <div class="card-tags"><span class="zone-badge">${escapeHtml(item.zone||"Cali")}</span>${multi}</div>
    <div class="card-specs">${specsHtml(item)}</div>
    ${sourceLinksHtml(item)}
    <div class="card-footer"><span class="card-date">${escapeHtml(seen)}</span>
      <a class="open-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Abrir aviso ↗</a>
    </div>
  </article>`;
}

function normalizedSearch(item){return[item.title,item.zone,item.description,...listingSources(item)].filter(Boolean).join(" ").toLocaleLowerCase("es")}
function updateZoneOptions(){
  const area=els.area.value;
  const zones=state.listings
    .filter(item=>!area||item.macro_zone===area)
    .map(item=>item.zone)
    .filter(z=>z&&z!=="Cali (zona por confirmar)");
  fillSelect(els.zone,zones);
  if(els.zone.value&&!zones.includes(els.zone.value))els.zone.value="";
}

function matchesCommonFilters(item,{ignoreArea=false,ignoreZone=false}={}){
  const q=els.search.value.trim().toLocaleLowerCase("es"),area=els.area.value,zone=els.zone.value,source=els.source.value;
  const minBeds=Number(els.beds.value||0),knownOnly=els.knownPrice.checked,budget=currentBudget();
  if(q&&!normalizedSearch(item).includes(q))return false;
  if(!ignoreArea&&area&&item.macro_zone!==area)return false;
  if(!ignoreZone&&zone&&item.zone!==zone)return false;
  if(source&&!listingSources(item).includes(source))return false;
  if(minBeds&&Number(item.bedrooms||0)<minBeds)return false;
  if(budget&&Number.isFinite(item.price)&&item.price>budget)return false;
  if(knownOnly&&!Number.isFinite(item.price))return false;
  return true;
}

function sortItems(items){
  const sort=els.sort.value;
  return [...items].sort((a,b)=>{
    if(sort==="recent")return(parseDate(b.last_seen)?.getTime()||0)-(parseDate(a.last_seen)?.getTime()||0);
    if(sort==="zone")return String(a.zone||"").localeCompare(String(b.zone||""),"es");
    const ap=Number.isFinite(a.price)?a.price:Number.MAX_SAFE_INTEGER,bp=Number.isFinite(b.price)?b.price:Number.MAX_SAFE_INTEGER;
    return ap-bp;
  });
}

function applyFilters(){
  let items=sortItems(state.listings.filter(item=>matchesCommonFilters(item)));
  let fallback=false;

  if(items.length===0&&els.area.value&&state.listings.length){
    items=sortItems(state.listings.filter(item=>matchesCommonFilters(item,{ignoreArea:true,ignoreZone:true}))).slice(0,6);
    fallback=items.length>0;
  }

  state.filtered=items;
  state.fallbackActive=fallback;
  renderListings();
  renderSources();

  if(fallback){
    els.status.hidden=false;
    els.status.textContent=`No encontré una coincidencia exacta en Zona ${els.area.value} con esos filtros. Te muestro alternativas disponibles en otras zonas de Cali para que no quedes sin opciones.`;
  }else{
    renderSourceStatus();
  }
}

function renderListings(){
  els.grid.innerHTML=state.filtered.map(cardHtml).join("");
  const empty=state.filtered.length===0;els.grid.hidden=empty;els.empty.hidden=!empty;
  els.count.textContent=`${state.filtered.length} de ${state.listings.length} avisos`;
}
function renderStats(){
  const prices=state.listings.map(x=>x.price).filter(Number.isFinite),zones=new Set(state.listings.map(x=>x.zone).filter(Boolean));
  const updated=state.data?.meta?.updated_at;
  els.statTotal.textContent=String(state.listings.length);els.statMin.textContent=prices.length?formatPrice(Math.min(...prices)):"—";
  els.statZones.textContent=String(zones.size);els.statUpdated.textContent=updated?relativeHours(updated):"—";
  els.lastUpdated.textContent=updated?`Actualizado ${shortDate(updated)}`:"Sin fecha";
}
function renderSourceStatus(){
  const sources=state.data?.meta?.sources||[];
  const failures=sources.filter(s=>s.ok===false&&s.automated!==false);
  if(failures.length){
    els.status.hidden=false;
    els.status.textContent=`Algunas fuentes no respondieron en la última ejecución: ${failures.map(s=>s.name).join(", ")}. Se conservaron avisos anteriores cuando fue posible.`;
  }else{
    els.status.hidden=true;
  }
}

function renderSources(){
  const sources=state.data?.meta?.sources||[];
  const automatic=sources.filter(s=>s.automated),manual=sources.filter(s=>!s.automated);
  if(els.sourceSummary)els.sourceSummary.textContent=`${automatic.length} fuentes automáticas${manual.length?` + ${manual.length} manual`:""}`;
  els.sourceLinks.innerHTML=sources.flatMap(source=>{
    const urls=Array.isArray(source.manual_urls)?source.manual_urls:[];
    const stateLabel=source.automated?(source.ok===false?" · revisar":source.skipped?" · en espera":" · activa"):" · manual";
    return urls.slice(0,2).map(url=>`<a class="source-link" href="${escapeHtml(safeHttpUrl(url))}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.name+stateLabel)} ↗</a>`);
  }).join("");
}

function resetFilters(){els.search.value="";els.area.value="";els.zone.value="";els.source.value="";els.beds.value="";els.sort.value="price";els.knownPrice.checked=false;els.budgetUnlimited.checked=true;els.budgetInput.value="";els.budgetRange.value=els.budgetRange.max;renderBudget();updateZoneOptions();applyFilters()}
function bindEvents(){
  [els.search,els.zone,els.source,els.beds,els.sort,els.knownPrice].forEach(el=>{el.addEventListener("input",applyFilters);el.addEventListener("change",applyFilters)});
  els.area.addEventListener("change",()=>{els.zone.value="";updateZoneOptions();applyFilters()});
  els.budgetRange.addEventListener("input",()=>setBudget(els.budgetRange.value,{fromRange:true}));
  els.budgetInput.addEventListener("input",()=>setBudget(els.budgetInput.value));
  els.budgetUnlimited.addEventListener("change",()=>{if(els.budgetUnlimited.checked)els.budgetInput.value="";renderBudget();applyFilters()});
  els.clear.addEventListener("click",resetFilters);els.emptyClear.addEventListener("click",resetFilters);
  els.themeBtn.addEventListener("click",()=>{const root=document.documentElement,next=root.dataset.theme==="light"?"dark":"light";root.dataset.theme=next;localStorage.setItem("cali-arriendos-theme",next)});
}
function initTheme(){const saved=localStorage.getItem("cali-arriendos-theme");if(["light","dark"].includes(saved))document.documentElement.dataset.theme=saved}
async function loadData(){
  try{
    const response=await fetch(`data/listings.json?v=${Date.now()}`,{cache:"no-store"});if(!response.ok)throw new Error(`HTTP ${response.status}`);
    const payload=await response.json();state.data=payload;state.listings=Array.isArray(payload.listings)?payload.listings:[];
    fillSelect(els.source,state.listings.flatMap(x=>listingSources(x)));updateZoneOptions();renderStats();renderBudget();renderSources();applyFilters();
  }catch(error){console.error(error);els.status.hidden=false;els.status.textContent="No se pudo cargar data/listings.json. Ejecuta el workflow de GitHub Actions o revisa la consola.";state.listings=[];applyFilters()}
}
document.addEventListener("DOMContentLoaded",()=>{initTheme();bindEvents();$("#footerYear").textContent=new Date().getFullYear();loadData()});
