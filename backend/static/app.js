'use strict';
const displayHcf = value => Number(value).toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2});
const message = document.getElementById('message');
function show(text, error=false) { message.hidden=false; message.className=error?'error':'success'; message.textContent=text; }
async function api(url, body, method='POST') {
  const response=await fetch(url,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
  return data;
}
function values(form) {
  const data=Object.fromEntries(new FormData(form));
  form.querySelectorAll('input[type=checkbox]').forEach(input=>data[input.name]=input.checked);
  form.querySelectorAll('input[type=number]').forEach(input=>{data[input.name]=input.value===''?null:input.value;});
  return data;
}
async function submit(form,action) {
  const button=form.querySelector('button'); button.disabled=true;
  try{await action();}catch(error){show(error.message,true);}finally{button.disabled=false;}
}
document.querySelectorAll('form[data-api]').forEach(form=>form.addEventListener('submit',event=>{
  event.preventDefault(); submit(form,async()=>{await api(form.dataset.api,values(form),form.dataset.method||'POST');location.assign(form.dataset.redirect||location.href);});
}));
const link=document.getElementById('link-form');
if(link) link.addEventListener('submit',event=>{event.preventDefault();submit(link,async()=>{const data=values(link);const id=data.driver_id;delete data.driver_id;await api(`/api/drivers/${id}/vehicles`,data,'PUT');location.assign('/ui/master-data?tab=drivers');});});
const driver=document.getElementById('entry-driver');
if(driver) driver.addEventListener('change',async()=>{
  const select=document.getElementById('entry-vehicle');select.replaceChildren(new Option('Fahrzeug auswählen',''));
  if(!driver.value)return;
  const chosen=driver.value;
  try{const rows=await api(`/api/drivers/${chosen}/vehicles`,undefined,'GET');if(driver.value!==chosen)return;
    rows.forEach(({vehicle:v,is_default})=>select.add(new Option(`F${v.id} · ${v.manufacturer} ${v.model} · ${v.class_code} · HCF ${displayHcf(v.hcf)}${is_default?' (Standard)':''}`,v.id,is_default,is_default)));
    if(!rows.length)show('Bitte zuerst unter Stammdaten ein Fahrzeug zuordnen.',true);
  }catch(error){show(error.message,true);}
});
const progress=document.getElementById('progress');
async function refreshProgress(){
  if(!progress)return;
  try{
    const groups=await api(`/api/events/${progress.dataset.event}/progress`,undefined,'GET');
    progress.replaceChildren();
    for(const g of groups){
      const section=document.createElement('section');section.className='class-card'+(g.ready?' success':'');
      const title=document.createElement('strong');title.textContent=`${g.class_code} · ${g.complete}/${g.total} bearbeitet`;section.append(title);
      const status=document.createElement('p');status.textContent=`${g.niw} NiW · ${g.ready?'Vollständig':(g.total-g.complete)+' offen'}`;section.append(status);
      for(const d of g.missing){const p=document.createElement('p');p.textContent=`#${d.start_number} ${d.name} · ${d.card_status==='missing'?'Bordkarte fehlt':'Werte unvollständig'}`;section.append(p);}
      if(g.ready){const a=document.createElement('a');a.href=`/print/events/${progress.dataset.event}/${encodeURIComponent(g.class_code)}`;a.target='_blank';a.textContent='Ergebnisliste drucken';section.append(a);}
      progress.append(section);
    }
    if(!groups.length)progress.textContent='Noch keine Nennungen.';
    document.getElementById('refresh-state').textContent='Aktualisiert: '+new Date().toLocaleTimeString('de-DE');
  }catch(error){document.getElementById('refresh-state').textContent='Aktualisierung fehlgeschlagen – angezeigte Werte können veraltet sein.';}
}
if(progress)setInterval(refreshProgress,5000);
const lookup=document.getElementById('lookup-form'),score=document.getElementById('score-form');
if(lookup)lookup.addEventListener('submit',event=>{event.preventDefault();submit(lookup,async()=>{
  document.getElementById('score-editor').hidden=true;
  const data=await api(`/api/events/${lookup.dataset.event}/entries/${lookup.elements.start_number.value}`,undefined,'GET');
  const e=data.entry;score.elements.entry_id.value=e.id;score.elements.version.value=e.version;score.elements.niw_reason.value=e.niw_reason;
  score.elements.card_status.value=data.sections.length?e.card_status:'received';
  document.getElementById('entry-heading').textContent=`#${e.start_number} · ${e.driver_name} · ${e.class_code} · HCF ${displayHcf(e.hcf)}`;
  const sections=document.getElementById('sections');sections.replaceChildren();
  for(let i=0;i<Number(lookup.dataset.count);i++){
    const box=document.createElement('div'),label=document.createElement('label'),input=document.createElement('input');
    label.textContent=`Sektionswert ${i+1}`;input.type='number';input.min='0';input.step='0.0001';input.dataset.points=i;input.value=data.sections[i]?.points??'';label.append(input);box.append(label);
    const check=document.createElement('label'),driven=document.createElement('input');check.className='check';driven.type='checkbox';driven.dataset.driven=i;driven.checked=data.sections[i]?.driven??true;check.append(driven,document.createTextNode('Sektion gefahren'));box.append(check);sections.append(box);
  }
  document.getElementById('score-editor').hidden=false;sections.querySelector('input').focus();
});});
if(score)score.addEventListener('submit',event=>{event.preventDefault();submit(score,async()=>{
  const sections=Array.from(score.querySelectorAll('[data-points]')).map(input=>({points:input.value===''?null:input.value,driven:score.querySelector(`[data-driven="${input.dataset.points}"]`).checked}));
  if(score.elements.card_status.value==='missing'&&sections.some(s=>s.points!==null))throw new Error('Bei fehlender Bordkarte dürfen keine Sektionswerte eingetragen sein.');
  const data={version:Number(score.elements.version.value),card_status:score.elements.card_status.value,niw_reason:score.elements.niw_reason.value,sections:score.elements.card_status.value==='received'?sections:[]};
  const result=await api(`/api/entries/${score.elements.entry_id.value}/scores`,data,'PUT');
  show(result.status==='niw'?'NiW gespeichert.':result.status==='complete'?'Bordkarte vollständig gespeichert.':'Zwischenstand gespeichert – Bordkarte bleibt offen.');
  document.getElementById('score-editor').hidden=true;lookup.reset();lookup.elements.start_number.focus();await refreshProgress();
});});

const vehicleForm=document.getElementById('vehicle-form');
if(vehicleForm){
  const mode=vehicleForm.elements.hcf_mode, kind=vehicleForm.elements.kind;
  const output=document.getElementById('hcf-preview');
  let revision=0, timer;
  function updateHcf(){
    const current=++revision;
    clearTimeout(timer);
    const sbs=kind.value==='sbs';
    mode.querySelector('option[value="auto"]').disabled=sbs;
    if(sbs)mode.value='manual';
    const manual=mode.value==='manual';
    document.getElementById('hcf-manual').hidden=!manual;
    vehicleForm.elements.hcf.required=manual;
    vehicleForm.elements.hcf_note.required=manual;
    for(const key of ['length_cm','width_cm','wheelbase_cm'])vehicleForm.elements[key].required=!manual;
    output.textContent=sbs?'Side-by-Side: manuelle Bestätigung erforderlich.':'Berechnung wird aktualisiert …';
    document.getElementById('hcf-formula').textContent='';
    document.getElementById('hcf-corrections').textContent='';
    if(sbs)return;
    timer=setTimeout(async()=>{
      const all=values(vehicleForm),data={};
      for(const key of ['kind','length_cm','width_cm','wheelbase_cm','front_lock','rear_lock','traction_control','closed_body'])data[key]=all[key];
      try{
        const result=await api('/api/hcf/preview',data);
        if(current!==revision)return;
        output.textContent=`Berechneter HCF: ${result.hcf.replace('.',',')} · Basis: ${displayHcf(result.base)}`;
        document.getElementById('hcf-formula').textContent=result.formula;
        document.getElementById('hcf-corrections').textContent=(result.corrections.map(c=>`${c.label}: ${c.percent>0?'+':''}${c.percent} %`).join(' · ')||'Keine Korrekturen')+` → insgesamt ${result.correction_percent} %`;
      }catch(error){if(current===revision)output.textContent=error.message;}
    },180);
  }
  for(const key of ['kind','length_cm','width_cm','wheelbase_cm','front_lock','rear_lock','traction_control','closed_body','hcf_mode'])vehicleForm.elements[key].addEventListener('input',updateHcf);
  updateHcf();
}

// Search all parts of a name independently, so first/last-name order does not matter.
const driverSearch=document.getElementById('entry-driver-search');
if(driverSearch && driver){
  const choices=Array.from(driver.options).filter(option=>option.value).map(option=>({value:option.value,text:option.text}));
  const info=document.getElementById('driver-search-info');
  driverSearch.addEventListener('input',()=>{
    const terms=driverSearch.value.toLocaleLowerCase('de-DE').replace(/#/g,'').trim().split(/\s+/).filter(Boolean);
    const matches=choices.filter(choice=>terms.every(term=>choice.text.toLocaleLowerCase('de-DE').includes(term)));
    const selected=driver.value;
    driver.replaceChildren(new Option(matches.length?'Bitte Fahrer auswählen':'Keine passenden Fahrer',''));
    matches.forEach(choice=>driver.add(new Option(choice.text,choice.value)));
    if(matches.some(choice=>choice.value===selected))driver.value=selected;
    else if(selected){driver.value='';driver.dispatchEvent(new Event('change'));}
    info.textContent=matches.length?`${matches.length} Fahrer gefunden. Bitte auswählen.`:'Keine Fahrer gefunden. Suche ändern oder Fahrer in der Datenbank anlegen.';
  });
}

const entryEdit=document.getElementById('entry-edit-form');
if(entryEdit){
  entryEdit.elements.vehicle_id.addEventListener('change',()=>{
    const option=entryEdit.elements.vehicle_id.selectedOptions[0];
    entryEdit.elements.class_code.value=option.dataset.class;
    entryEdit.elements.hcf.value=option.dataset.hcf;
  });
}
