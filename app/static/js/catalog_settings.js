const state={tipos:[],sectores:[],personas:[]};
const $=s=>document.querySelector(s);
const $$=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));

document.addEventListener("DOMContentLoaded",async()=>{
  $$(".tabs button").forEach(b=>b.onclick=()=>mostrarTab(b.dataset.tab));
  $$("[data-new]").forEach(b=>b.onclick=()=>abrirNuevo(b.dataset.new));
  $$("[data-close]").forEach(b=>b.onclick=()=>b.closest(".backdrop").classList.add("hidden"));
  $("#form-tipo").onsubmit=guardarTipo;
  $("#form-sector").onsubmit=guardarSector;
  $("#form-persona").onsubmit=guardarPersona;
  await cargar();
});

async function api(url,options={}){
  const r=await fetch(url,{headers:{"Content-Type":"application/json"},...options});
  if(!r.ok){let d={};try{d=await r.json()}catch{}throw new Error(d.detail||"No se pudo completar la operación")}
  return r.status===204?null:r.json();
}
async function cargar(){
  const d=await api("/api/catalogos");
  state.tipos=d.tipos_inventario;state.sectores=d.sectores;state.personas=d.personas;
  render();
}
function mostrarTab(tab){
  $$(".tabs button").forEach(b=>b.classList.toggle("active",b.dataset.tab===tab));
  ["tipos","personas","sectores"].forEach(x=>$("#panel-"+x).classList.toggle("hidden",x!==tab));
}
function estado(v){return `<span class="pill ${v?"":"off"}">${v?"Activo":"Inactivo"}</span>`}
function render(){
  $("#tabla-tipos").innerHTML=state.tipos.map(x=>`<tr><td><b>${esc(x.nombre)}</b><span class="muted">${esc(x.descripcion||x.codigo)}</span></td><td>${esc(x.motor)}</td><td>${x.modalidad==="MEDIOS"?"Vacíos, llenos y rotos":"Estándar"}</td><td>${esc(x.formato_impresion)}</td><td>${estado(x.activo)}</td><td><button class="edit" onclick="editarTipo('${esc(x.codigo)}')">Editar</button></td></tr>`).join("");
  $("#tabla-sectores").innerHTML=state.sectores.map(x=>`<tr><td><b>${esc(x.nombre)}</b></td><td>${esc(x.descripcion||"—")}</td><td>${x.personas}</td><td>${estado(x.activo)}</td><td><button class="edit" onclick="editarSector(${x.id})">Editar</button></td></tr>`).join("");
  $("#tabla-personas").innerHTML=state.personas.map(x=>`<tr><td><b>${esc(x.nombre)}</b></td><td>${esc(x.sector||"Sin sector")}</td><td>${esc(x.legajo||"—")}</td><td>${esc(x.contacto||"—")}</td><td>${estado(x.activo)}</td><td><button class="edit" onclick="editarPersona(${x.id})">Editar</button></td></tr>`).join("");
  $("#persona-sector").innerHTML='<option value="">Sin sector</option>'+state.sectores.filter(x=>x.activo).map(x=>`<option value="${x.id}">${esc(x.nombre)}</option>`).join("");
}
function abrir(id){$("#modal-"+id).classList.remove("hidden")}
function abrirNuevo(tipo){
  if(tipo==="tipo"){$("#form-tipo").reset();$("#tipo-codigo").value="";$("#tipo-orden").value=100;$("#tipo-activo").checked=true;$("#titulo-tipo").textContent="Nuevo tipo"}
  if(tipo==="sector"){$("#form-sector").reset();$("#sector-id").value="";$("#sector-orden").value=100;$("#sector-activo").checked=true;$("#titulo-sector").textContent="Nuevo sector"}
  if(tipo==="persona"){$("#form-persona").reset();$("#persona-id").value="";$("#persona-orden").value=100;$("#persona-activa").checked=true;$("#titulo-persona").textContent="Nueva persona"}
  abrir(tipo);
}
window.editarTipo=c=>{const x=state.tipos.find(v=>v.codigo===c);$("#tipo-codigo").value=x.codigo;$("#tipo-nombre").value=x.nombre;$("#tipo-descripcion").value=x.descripcion;$("#tipo-motor").value=x.motor;$("#tipo-modalidad").value=x.modalidad;$("#tipo-formato").value=x.formato_impresion;$("#tipo-orden").value=x.orden;$("#tipo-activo").checked=x.activo;$("#titulo-tipo").textContent="Editar tipo";abrir("tipo")};
window.editarSector=id=>{const x=state.sectores.find(v=>v.id===id);$("#sector-id").value=x.id;$("#sector-nombre").value=x.nombre;$("#sector-descripcion").value=x.descripcion;$("#sector-orden").value=x.orden;$("#sector-activo").checked=x.activo;$("#titulo-sector").textContent="Editar sector";abrir("sector")};
window.editarPersona=id=>{const x=state.personas.find(v=>v.id===id);$("#persona-id").value=x.id;$("#persona-nombre").value=x.nombre;$("#persona-sector").value=x.sector_id||"";$("#persona-legajo").value=x.legajo;$("#persona-contacto").value=x.contacto;$("#persona-orden").value=x.orden;$("#persona-activa").checked=x.activo;$("#titulo-persona").textContent="Editar persona";abrir("persona")};
async function enviar(form,url,payload,id){
  try{await api(url,{method:id?"PUT":"POST",body:JSON.stringify(payload)});form.closest(".backdrop").classList.add("hidden");await cargar();toast("Cambios guardados")}
  catch(e){toast(e.message,true)}
}
function guardarTipo(e){e.preventDefault();const id=$("#tipo-codigo").value;enviar(e.currentTarget,id?"/api/tipos-inventario/"+encodeURIComponent(id):"/api/tipos-inventario",{nombre:$("#tipo-nombre").value.trim(),descripcion:$("#tipo-descripcion").value.trim(),motor:$("#tipo-motor").value,modalidad:$("#tipo-modalidad").value,formato_impresion:$("#tipo-formato").value,orden:Number($("#tipo-orden").value),activo:$("#tipo-activo").checked},id)}
function guardarSector(e){e.preventDefault();const id=$("#sector-id").value;enviar(e.currentTarget,id?"/api/sectores/"+id:"/api/sectores",{nombre:$("#sector-nombre").value.trim(),descripcion:$("#sector-descripcion").value.trim(),orden:Number($("#sector-orden").value),activo:$("#sector-activo").checked},id)}
function guardarPersona(e){e.preventDefault();const id=$("#persona-id").value;enviar(e.currentTarget,id?"/api/personas/"+id:"/api/personas",{nombre:$("#persona-nombre").value.trim(),sector_id:$("#persona-sector").value?Number($("#persona-sector").value):null,legajo:$("#persona-legajo").value.trim(),contacto:$("#persona-contacto").value.trim(),orden:Number($("#persona-orden").value),activo:$("#persona-activa").checked},id)}
function toast(msg,error=false){const x=$("#toast");x.textContent=msg;x.classList.toggle("error",error);x.classList.remove("hidden");setTimeout(()=>x.classList.add("hidden"),3000)}
