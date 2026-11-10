'use strict';
const $=id=>document.getElementById(id),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels={pacientes:'Pacientes',pessoas:'Profissionais e fornecedores',agenda:'Agenda',clinico:'Prontuário',titulos:'Contas a pagar / receber',pagamentos:'Pagamentos e estornos',materiais:'Materiais',movimentos:'Movimentações de estoque'};
const specs={
 pacientes:[['nome','Nome','text'],['matricula','Matrícula única (texto)','text'],['telefone','Telefone','text',false],['responsavel','Responsável legal','text',false],['ativo','Situação',['Ativo','Inativo']]],
 pessoas:[['nome','Nome','text'],['tipo','Tipo',['profissional','fornecedor']],['registro','Registro profissional / referência','text',false],['ativo','Situação',['Ativo','Inativo']]],
 agenda:[['paciente','Paciente','@pacientes'],['profissional','Profissional','@pessoas'],['sala','Sala / cadeira','text'],['inicio','Início (Brasília)','datetime-local'],['fim','Fim (Brasília)','datetime-local'],['status','Situação',['agendado','confirmado','chegou','atendido','faltou','cancelado']],['motivo','Motivo da remarcação ou cancelamento','text',false]],
 clinico:[['paciente','Paciente','@pacientes'],['tipo','Tipo',['anamnese','evolucao','plano','consentimento','correcao']],['conteudo','Registro clínico / respostas da anamnese','textarea'],['referencia','Registro anterior corrigido (opcional)','@clinico',false]],
 titulos:[['descricao','Descrição sem dados clínicos','text'],['tipo','Tipo',['receber','pagar']],['valor','Valor em reais','money'],['vencimento','Vencimento','date']],
 pagamentos:[['titulo','Conta','@titulos'],['valor','Valor em reais','money'],['tipo','Tipo',['pagamento','estorno']],['referencia','Pagamento original (para estorno)','@pagamentos',false],['motivo','Método / motivo / referência','text']],
 materiais:[['nome','Nome do material','text'],['codigo','Código único','text'],['unidade','Unidade (ex.: unidade, caixa)','text'],['minimo','Estoque mínimo (inteiro)','number'],['ativo','Situação',['Ativo','Inativo']]],
 movimentos:[['material','Material','@materiais'],['lote','Lote','text'],['validade','Validade do lote','date'],['tipo','Tipo',['entrada','saida']],['quantidade','Quantidade inteira','number'],['motivo','Motivo / fornecedor / atendimento','text']]
};
labels.funcionarios='Funcionários';
specs.funcionarios=[['nome','Nome completo','text'],['matricula','Matrícula (preserva zeros)','text'],['cargo','Cargo / função','text'],['registro','Registro profissional, se aplicável','text',false],['ativo','Situação',['Ativo','Inativo']]];
let vaultNamespace=localStorage.getItem('clinica-installation')||'legacy';
let vault=null,key=null,salt=null,current='pacientes',editing=null,busy=false,storage=null,lastActivity=Date.now();
const enc=new TextEncoder(),dec=new TextDecoder();
function message(t){$('message').textContent=t;}
function db(){return new Promise((res,rej)=>{const r=indexedDB.open('clinica-cofre-v1',1);r.onupgradeneeded=()=>r.result.createObjectStore('vaults');r.onsuccess=()=>res(r.result);r.onerror=()=>rej(r.error);});}
async function getVault(name){storage=storage||await db();return new Promise((res,rej)=>{const r=storage.transaction('vaults').objectStore('vaults').get(vaultNamespace+':'+name);r.onsuccess=()=>res(r.result);r.onerror=()=>rej(r.error);});}
async function setVault(name,value){storage=storage||await db();return new Promise((res,rej)=>{const tx=storage.transaction('vaults','readwrite');value?tx.objectStore('vaults').put(value,vaultNamespace+':'+name):tx.objectStore('vaults').delete(vaultNamespace+':'+name);tx.oncomplete=res;tx.onerror=()=>rej(tx.error);tx.onabort=()=>rej(tx.error);});}
async function derive(password,s){const material=await crypto.subtle.importKey('raw',enc.encode(password),'PBKDF2',false,['deriveKey']);return crypto.subtle.deriveKey({name:'PBKDF2',salt:new Uint8Array(s),iterations:310000,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);}
async function save(){const iv=crypto.getRandomValues(new Uint8Array(12));const cipher=await crypto.subtle.encrypt({name:'AES-GCM',iv},key,enc.encode(JSON.stringify(vault)));await setVault(vault.user.name,{salt:Array.from(salt),iv:Array.from(iv),cipher:Array.from(new Uint8Array(cipher))});}
async function unlock(name,password){const blob=await getVault(name);if(!blob)return null;salt=new Uint8Array(blob.salt);key=await derive(password,salt);try{return JSON.parse(dec.decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:new Uint8Array(blob.iv)},key,new Uint8Array(blob.cipher))));}catch{throw Error('Não foi possível abrir o cofre. Confira a senha; não apague alterações pendentes.');}}
async function api(path,body){let r;try{r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-Clinica-Request':'1'}:{},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(15000)});}catch{throw Error('Sem conexão com o servidor. Alterações permanecem no cofre local.');}const d=await r.json();if(!r.ok)throw Error(d.error||'Falha no servidor.');return d;}
async function login(offline){
 const name=$('username').value.trim().toLowerCase(),password=$('password').value;
 try{
  if(!crypto.subtle)throw Error('Este aparelho precisa de HTTPS para funcionar com proteção offline.');
  if(!offline){const config=await api('setup');vaultNamespace=config.installation;localStorage.setItem('clinica-installation',vaultNamespace);}
  let cached=await unlock(name,password);
  if(offline){
   if(!cached)throw Error('Primeiro entre online e sincronize neste aparelho.');
   if(Date.now()-cached.verified>8*3600000||Date.now()<cached.verified)throw Error('Prazo offline encerrado. Faça login online novamente.');
   vault=cached;
  }else{
   await api('login',{name,password});const state=await api('state');
   if(cached&&cached.user.id!==state.user.id)throw Error('Conta diferente da cópia local. Confira antes de continuar.');
   if(!cached){salt=crypto.getRandomValues(new Uint8Array(16));key=await derive(password,salt);}
   vault={user:state.user,records:state.records,queue:cached?.queue||[],verified:Date.now()};await save();
  }
  $('password').value='';$('login').hidden=true;$('workspace').hidden=false;current=Object.keys(vault.records)[0];lastActivity=Date.now();render();message(offline?'Cofre offline aberto. Alterações ainda precisam de validação online.':'Entrada realizada. Sincronize a fila pendente quando necessário.');
 }catch(e){message(e.message);}
}
$('loginForm').onsubmit=e=>{e.preventDefault();login(false);};$('offline').onclick=()=>login(true);
function guard(){if(!vault)throw Error('Entre no sistema.');if(Date.now()-vault.verified>8*3600000||Date.now()<vault.verified)throw Error('Prazo offline encerrado. Entre online novamente.');}
function projected(){const data=structuredClone(vault.records);for(const op of vault.queue){if(!data[op.kind])continue;const list=data[op.kind],i=list.findIndex(x=>x.id===op.record);const item={id:op.record,data:op.data,version:op.base+1,updated:'Pendente',author:vault.user.id};if(i<0)list.unshift(item);else list[i]=item;}return data;}
function displayRef(id,data){for(const rows of Object.values(data)){const r=rows.find(x=>x.id===id);if(r)return r.data.nome||r.data.descricao||(r.data.tipo+' · '+r.updated);}return id||'';}
const money=n=>(n/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
function render(){
 if(!vault)return;const data=projected();$('identity').textContent=vault.user.name+' · '+vault.user.role;$('connection').textContent=(navigator.onLine?'Rede disponível (servidor a verificar)':'Sem rede')+' · '+vault.queue.length+' pendente(s)';$('admin').hidden=vault.user.role!=='administrador';
 $('nav').innerHTML=Object.keys(data).map(k=>'<button data-kind="'+k+'" class="'+(current===k?'active':'')+'">'+labels[k]+'</button>').join('');
 $('title').textContent=labels[current];$('hint').textContent=current==='clinico'?'Registros são imutáveis após salvar. Use Correção e referencie o registro anterior. Anamnese: alergias, medicamentos, condições e demais informações pertinentes.':current==='agenda'?'Remarcação: edite início e fim e informe o motivo. Todos os horários são da clínica, em Brasília.':current==='movimentos'?'Saldo confirmado é calculado no servidor; movimentos offline ficam sujeitos a validação.':'Registros pendentes ainda não foram confirmados pelo servidor.';
 const search=$('search').value.toLocaleLowerCase();const rows=(data[current]||[]).filter(r=>JSON.stringify(r.data).toLocaleLowerCase().includes(search));const fields=specs[current];
 $('list').innerHTML=rows.length?'<table><thead><tr>'+fields.map(f=>'<th>'+esc(f[1])+'</th>').join('')+'<th>Situação / ação</th></tr></thead><tbody>'+rows.map(r=>'<tr>'+fields.map(([k,,type])=>{let v=r.data[k];if(typeof type==='string'&&type.startsWith('@'))v=displayRef(v,data);if(type==='money')v=money(v);if(k==='ativo')v=v?'Ativo':'Inativo';return '<td>'+esc(v)+'</td>';}).join('')+'<td>'+esc(r.updated==='Pendente'?'Pendente':'Confirmado')+(!['clinico','pagamentos','movimentos','titulos'].includes(current)?'<br><button data-edit="'+r.id+'">Editar</button>':'')+'</td></tr>').join('')+'</tbody></table>':'<p>Nenhum registro. Cadastre apenas dados fictícios nesta fase.</p>';
 $('queue').innerHTML=vault.queue.length?vault.queue.map((op,i)=>'<div class="pending"><b>'+esc(labels[op.kind])+'</b> · '+esc(op.data.nome||op.data.descricao||op.data.tipo||'Registro')+'<p class="error">'+esc(op.error||'Aguardando sincronização')+'</p><button class="secondary" data-discard="'+i+'">Descartar esta e posteriores</button></div>').join(''):'<p>Sem alterações locais pendentes.</p>';
 const cards=[];if(data.pacientes)cards.push([data.pacientes.filter(x=>x.data.ativo).length,'pacientes ativos']);if(data.agenda){const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo'}).format(new Date());cards.push([data.agenda.filter(x=>x.data.inicio.startsWith(today)&&x.data.status!=='cancelado').length,'consultas hoje']);}
 if(data.titulos){for(const type of ['receber','pagar']){const total=data.titulos.filter(x=>x.data.tipo===type).reduce((s,t)=>s+t.data.valor-(data.pagamentos||[]).filter(p=>p.data.titulo===t.id).reduce((n,p)=>n+(p.data.tipo==='pagamento'?1:-1)*p.data.valor,0),0);cards.push([money(total),type==='receber'?'saldo a receber':'saldo a pagar']);}}
 if(data.materiais){const balances={};for(const m of data.movimentos||[])balances[m.data.material]=(balances[m.data.material]||0)+(m.data.tipo==='entrada'?1:-1)*m.data.quantidade;cards.push([data.materiais.filter(m=>m.data.ativo&&(balances[m.id]||0)<m.data.minimo).length,'materiais abaixo do mínimo']);const lots={};for(const r of data.movimentos||[]){const k=r.data.material+'|'+r.data.lote;lots[k]??={saldo:0,validade:r.data.validade};lots[k].saldo+=(r.data.tipo==='entrada'?1:-1)*r.data.quantidade;}const limit=new Date(Date.now()+30*86400000).toISOString().slice(0,10);cards.push([Object.values(lots).filter(l=>l.saldo>0&&l.validade<=limit).length,'lotes vencidos / vencendo em 30 dias']);}
 $('dashboard').innerHTML='<h2>Visão da clínica</h2><div class="cards">'+cards.map(([n,t])=>'<div class="card"><b>'+esc(n)+'</b>'+esc(t)+'</div>').join('')+'</div><p class="muted">Inclui alterações locais provisórias. Confira a fila antes de usar os totais.</p>';
}
$('nav').onclick=e=>{if(e.target.dataset.kind){current=e.target.dataset.kind;$('search').value='';render();}};$('search').oninput=render;
function editor(id){
 try{guard();}catch(e){message(e.message);return;}
 const data=projected();editing=(data[current]||[]).find(r=>r.id===id)||null;$('editTitle').textContent=(editing?'Editar: ':'Novo: ')+labels[current];
 $('fields').innerHTML=specs[current].map(([k,label,type,required=true])=>{
  let v=editing?.data[k]??'';if(k==='ativo')v=v===false?'Inativo':'Ativo';if(type==='money'&&v!=='')v=(v/100).toFixed(2);const attr=' name="'+k+'" '+(required?'required':'');let field;
  if(Array.isArray(type))field='<select'+attr+'>'+type.map(t=>'<option '+(v===t?'selected':'')+'>'+esc(t)+'</option>').join('')+'</select>';
  else if(type.startsWith('@')){const options=(data[type.slice(1)]||[]).filter(r=>r.data.ativo!==false&&(k!=='profissional'||r.data.tipo==='profissional'));field='<select'+attr+'><option value="">Selecione</option>'+options.map(r=>'<option value="'+r.id+'" '+(v===r.id?'selected':'')+'>'+esc(displayRef(r.id,data))+'</option>').join('')+'</select>';}
  else if(type==='textarea')field='<textarea'+attr+' maxlength="12000">'+esc(v)+'</textarea>';
  else field='<input'+attr+' type="'+(type==='money'?'number':type)+'" '+(type==='money'?'step="0.01" min="0.01"':type==='number'?'step="1" min="0"':'')+' value="'+esc(v)+'">';
  return '<label>'+esc(label)+field+'</label>';
 }).join('');$('editor').showModal();
}
$('new').onclick=()=>editor();$('cancel').onclick=()=>$('editor').close();$('list').onclick=e=>{if(e.target.dataset.edit)editor(e.target.dataset.edit);};
$('editForm').onsubmit=async e=>{
 e.preventDefault();if(busy)return;busy=true;
 try{guard();const values=Object.fromEntries(new FormData(e.target));for(const [k,,type] of specs[current]){if(type==='number')values[k]=Number(values[k]);if(type==='money'){const v=values[k];if(!/^\d+(\.\d{1,2})?$/.test(v))throw Error('Valor monetário inválido.');values[k]=Math.round(Number(v)*100);}if(k==='ativo')values[k]=values[k]==='Ativo';}
 const op={id:crypto.randomUUID(),record:editing?.id||crypto.randomUUID(),base:editing?.version||0,kind:current,data:values};vault.queue.push(op);
 try{await save();}catch(err){vault.queue.pop();throw Error('Falha ao salvar no aparelho. Nada confirmado; libere espaço e tente novamente.');}
 $('editor').close();render();message('Salvo no cofre local. Sincronize para validar e confirmar.');
 }catch(err){message(err.message);}finally{busy=false;}
};
async function sync(){
 if(busy)return;busy=true;$('sync').disabled=true;
 try{guard();const state=await api('state');if(state.user.id!==vault.user.id)throw Error('Sessão pertence a outro usuário. Bloqueie e entre novamente.');
 vault.user=state.user;vault.records=state.records;
 const batch=vault.queue.slice(0,100).map(({error,...op})=>op);
 if(batch.length){const res=await api('sync',{operations:batch});vault.records=res.records;for(const result of res.results){const i=vault.queue.findIndex(x=>x.id===result.id);if(i<0)continue;if(result.ok)vault.queue.splice(i,1);else vault.queue[i].error=result.error;}}
 await save();render();message(vault.queue.length?'Há pendências. Confira os avisos; nenhum conflito foi sobrescrito.':'Sincronização concluída.');
 }catch(e){message(e.message);}finally{busy=false;$('sync').disabled=false;}
}
$('sync').onclick=sync;
$('queue').onclick=async e=>{if(e.target.dataset.discard===undefined||busy)return;const i=Number(e.target.dataset.discard);if(!confirm('Descartar esta alteração e todas as posteriores deste aparelho? Os registros já confirmados no servidor serão preservados.'))return;const previous=vault.queue;vault.queue=previous.slice(0,i);try{await save();render();}catch{vault.queue=previous;message('Não foi possível gravar. Fila preservada.');}};
function lockScreen(){if(busy)return;$('editor').close();vault=null;key=null;salt=null;$('fields').innerHTML='';$('list').innerHTML='';$('queue').innerHTML='';$('dashboard').innerHTML='';$('adminResult').textContent='';$('workspace').hidden=true;$('login').hidden=false;$('identity').textContent='Bloqueado';message('Tela bloqueada. Alterações salvas permanecem criptografadas neste aparelho.');}
$('lock').onclick=lockScreen;
$('erase').onclick=async()=>{if(busy)return;if(!confirm(vault.queue.length?'Existem pendências. Apagar o cofre perderá essas alterações. Confirma?':'Apagar a cópia local e sair?'))return;try{await api('logout',{});}catch{}await setVault(vault.user.name,null);lockScreen();message('Cofre local apagado.');};
for(const ev of ['pointerdown','keydown'])document.addEventListener(ev,()=>lastActivity=Date.now());setInterval(()=>{if(vault&&Date.now()-lastActivity>300000)lockScreen();},10000);
window.addEventListener('online',()=>{render();if(vault)message('Conexão detectada. Clique em Sincronizar.');});window.addEventListener('offline',render);
$('backup').onclick=async()=>{try{const r=await api('backup',{});message(r.message+' Arquivo: '+r.file);}catch(e){message(e.message);}};
$('audit').onclick=async()=>{try{$('adminResult').textContent=JSON.stringify((await api('audit')).audit,null,2);}catch(e){message(e.message);}};
$('users').onclick=()=>{
 const dialog=document.createElement('dialog');const form=document.createElement('form');
 form.innerHTML='<h2>Cadastrar usuário de acesso</h2><p>Cadastrar funcionário não cria acesso automaticamente. Escolha o perfil conforme a função.</p><label>Usuário<input name="name" required pattern="[a-z0-9._-]{3,40}" minlength="3" maxlength="40" autocomplete="off"></label><label>Perfil<select name="role"><option value="recepcao">Recepção</option><option value="dentista">Dentista</option><option value="financeiro">Financeiro</option><option value="estoque">Estoque</option><option value="administrador">Administrador</option></select></label><label>Senha (mínimo 12 caracteres)<input name="password" type="password" minlength="12" maxlength="200" required autocomplete="new-password"></label><label>Repita a senha<input name="confirm" type="password" minlength="12" required autocomplete="new-password"></label><p class="error" role="alert"></p><button type="submit">Confirmar cadastro</button> <button type="button">Cancelar</button>';
 dialog.append(form);document.body.append(dialog);form.querySelector('[type=button]').onclick=()=>dialog.remove();
 form.onsubmit=async e=>{e.preventDefault();const f=new FormData(form),button=form.querySelector('[type=submit]');if(f.get('password')!==f.get('confirm')){form.querySelector('[role=alert]').textContent='As senhas não conferem.';return;}button.disabled=true;
 try{await api('users',{name:f.get('name'),role:f.get('role'),password:f.get('password')});dialog.remove();message('Usuário cadastrado. Já pode entrar online com o acesso escolhido.');}
 catch(err){form.querySelector('[role=alert]').textContent=err.message;button.disabled=false;}};
 dialog.showModal();
};
$('print').onclick=()=>window.print();
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>message('Não foi possível preparar a abertura offline. Verifique HTTPS e permissões do navegador.'));

async function setupScreen(){
 try{const config=await api('setup');$('firstSetup').hidden=!config.needed;$('login').hidden=config.needed;if(config.adminPending)message('O administrador online ainda precisa ser configurado pelo responsável pela implantação.');}catch(e){message('Servidor não disponível. Abra INICIAR.cmd; o desbloqueio offline requer um acesso anterior.');}
}
$('setupForm').onsubmit=async e=>{
 e.preventDefault();const button=$('setupSubmit');button.disabled=true;
 try{const f=new FormData(e.target);await api('setup',{name:f.get('name'),password:f.get('password'),confirm:f.get('confirm'),examples:f.get('examples')==='on'});$('username').value=f.get('name');e.target.reset();await setupScreen();message('Administrador criado. Digite sua senha e clique em Entrar online.');}
 catch(err){message(err.message);}finally{button.disabled=false;}
};
setupScreen();
