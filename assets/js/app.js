const state={data:null,listings:[],filtered:[]};
const $=s=>document.querySelector(s);
const els={
  grid:$("#listingsGrid"),empty:$("#emptyState"),emptyClear:$("#emptyClear"),search:$("#searchInput"),
  zone:$("#zoneFilter"),source:$("#sourceFilter"),beds:$("#bedFilter"),sort:$("#sortFilter"),
  knownPrice:$("#knownPriceOnly"),clear:$("#clearFilters"),count:$("#resultCount"),status:$("#statusBox"),
  lastUpdated:$("#lastUpdated"),statTotal:$("#statTotal"),statMin:$("#statMin"),statZones:$("#statZones"),
  statUpdated:$("#statUpdated"),sourceLinks:$("#sourceLinks"),themeBtn:$("#themeBtn")
};
const money=new Intl.NumberFormat("es-CO",{style:"currency",currency:"COP",maximumFractionDigits:0});

function escapeHtml(v=""){return String(v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;")}
function safeHttpUrl(v){try{const u=new URL(v);return["http:","https:"].includes(u.protocol)?u.href:"#"}catch{return"#"}}
function formatPrice(p){return Number.isFinite(p)?money.format(p):"Precio por revisar"}
function parseDate(v){const d=new Date(v);return Number.isNaN(d.getTime())?null:d}
function shortDate(v){const d=parseDate(v);if(!d)return"fecha no disponible";return new Intl.DateTimeFormat("es-CO",{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}).format(d)}
function relativeHours(v){const d=parseDate(v);if(!d)return"—";const h=Math.max(0,Math.round((Date.now()-d.getTime())/36e5));if(h<1)return"<1 h";if(h<24)return`${h} h`;return`${Math.round(h/24)} d`}

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

function cardHtml(item){
  const url=safeHttpUrl(item.url);
  const stale=item.stale?'<span class="stale-badge">por revisar</span>':"";
  const priceClass=Number.isFinite(item.price)?"":" price-unknown";
  const seen=item.last_seen?`Visto ${shortDate(item.last_seen)}`:"Visto recientemente";
  return `<article class="listing-card">
    <div class="card-top"><span class="source-name">${escapeHtml(item.source||"Web")}</span>${stale}</div>
    <strong class="card-price${priceClass}">${escapeHtml(formatPrice(item.price))}</strong>
    <h3 class="card-title">${escapeHtml(item.title||"Apartamento en arriendo")}</h3>
    <div class="card-tags"><span class="zone-badge">${escapeHtml(item.zone||"Sur de Cali")}</span></div>
    <div class="card-specs">${specsHtml(item)}</div>
    <div class="card-footer"><span class="card-date">${escapeHtml(seen)}</span>
      <a class="open-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Abrir aviso ↗</a>
    </div>
  </article>`;
}

function normalizedSearch(item){return[item.title,item.zone,item.source,item.description].filter(Boolean).join(" ").toLocaleLowerCase("es")}
function applyFilters(){
  const q=els.search.value.trim().toLocaleLowerCase("es"),zone=els.zone.value,source=els.source.value;
  const minBeds=Number(els.beds.value||0),knownOnly=els.knownPrice.checked,sort=els.sort.value;
  let items=state.listings.filter(item=>{
    if(q&&!normalizedSearch(item).includes(q))return false;
    if(zone&&item.zone!==zone)return false;
    if(source&&item.source!==source)return false;
    if(minBeds&&Number(item.bedrooms||0)<minBeds)return false;
    if(knownOnly&&!Number.isFinite(item.price))return false;
    return true;
  });
  items=[...items].sort((a,b)=>{
    if(sort==="recent")return(parseDate(b.last_seen)?.getTime()||0)-(parseDate(a.last_seen)?.getTime()||0);
    if(sort==="zone")return String(a.zone||"").localeCompare(String(b.zone||""),"es");
    const ap=Number.isFinite(a.price)?a.price:Number.MAX_SAFE_INTEGER,bp=Number.isFinite(b.price)?b.price:Number.MAX_SAFE_INTEGER;
    return ap-bp;
  });
  state.filtered=items;renderListings();
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
function renderSources(){
  const sources=state.data?.meta?.sources||[];
  els.sourceLinks.innerHTML=sources.flatMap(source=>{
    const urls=Array.isArray(source.manual_urls)?source.manual_urls:[];
    return urls.slice(0,3).map((url,i)=>{
      const label=urls.length>1?`${source.name} ${i+1}`:source.name;
      return `<a class="source-link" href="${escapeHtml(safeHttpUrl(url))}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)} ↗</a>`;
    });
  }).join("");
  const failures=sources.filter(s=>s.ok===false&&s.automated!==false);
  if(failures.length){els.status.hidden=false;els.status.textContent=`Algunas fuentes no respondieron en la última ejecución: ${failures.map(s=>s.name).join(", ")}. Se conservaron avisos anteriores cuando fue posible.`}
  else els.status.hidden=true;
}
function resetFilters(){els.search.value="";els.zone.value="";els.source.value="";els.beds.value="";els.sort.value="price";els.knownPrice.checked=false;applyFilters()}
function bindEvents(){
  [els.search,els.zone,els.source,els.beds,els.sort,els.knownPrice].forEach(el=>{el.addEventListener("input",applyFilters);el.addEventListener("change",applyFilters)});
  els.clear.addEventListener("click",resetFilters);els.emptyClear.addEventListener("click",resetFilters);
  els.themeBtn.addEventListener("click",()=>{const root=document.documentElement,next=root.dataset.theme==="light"?"dark":"light";root.dataset.theme=next;localStorage.setItem("cali-arriendos-theme",next)});
}
function initTheme(){const saved=localStorage.getItem("cali-arriendos-theme");if(["light","dark"].includes(saved))document.documentElement.dataset.theme=saved}
async function loadData(){
  try{
    const response=await fetch(`data/listings.json?v=${Date.now()}`,{cache:"no-store"});if(!response.ok)throw new Error(`HTTP ${response.status}`);
    const payload=await response.json();state.data=payload;state.listings=Array.isArray(payload.listings)?payload.listings:[];
    fillSelect(els.zone,state.listings.map(x=>x.zone));fillSelect(els.source,state.listings.map(x=>x.source));renderStats();renderSources();applyFilters();
  }catch(error){console.error(error);els.status.hidden=false;els.status.textContent="No se pudo cargar data/listings.json. Ejecuta el workflow de GitHub Actions o revisa la consola.";state.listings=[];applyFilters()}
}
document.addEventListener("DOMContentLoaded",()=>{initTheme();bindEvents();$("#footerYear").textContent=new Date().getFullYear();loadData()});
