'use strict';
// A recuperação importa somente operações; nunca restaura o retrato antigo do banco.
function recoveryPlan(old,current,allowed,archive){
 if(!old||old.user?.id!==current.user.id||old.user?.name!==current.user.name)throw Error('Esta cópia pertence a outra conta.');
 if(!Array.isArray(old.queue)||old.queue.length>1000)throw Error('Fila antiga inválida ou muito grande. Preserve a cópia para suporte.');
 if((current.recoveredArchives||[]).includes(archive))throw Error('Esta cópia já foi recuperada. Não será importada novamente.');
 const stable=x=>JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
 const normalize=o=>({id:o.id,record:o.record,base:o.base,kind:o.kind,data:o.data});
 const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
 const known=new Map(current.queue.map(o=>[o.id,normalize(o)])),added=[];
 for(const raw of old.queue){
  if(!raw||!uuid.test(raw.id)||!uuid.test(raw.record)||!Number.isInteger(raw.base)||raw.base<0||!raw.data||typeof raw.data!=='object'||Array.isArray(raw.data)||typeof raw.kind!=='string')throw Error('Operação antiga inválida. Nenhuma alteração foi recuperada.');
  if(!Object.hasOwn(allowed,raw.kind))throw Error('Seu perfil atual não permite recuperar todos os módulos desta cópia.');
  const op=normalize(raw);if(JSON.stringify(op).length>25000)throw Error('Operação antiga excede o limite.');
  if(known.has(op.id)){if(stable(known.get(op.id))!==stable(op))throw Error('Há operações com o mesmo identificador e conteúdo diferente. Preserve as cópias para suporte.');continue;}
  known.set(op.id,op);added.push(op);
 }
 return added;
}
async function recoveryArchives(name){
 storage=storage||await db();const prefix=vaultNamespace+':'+name+':recuperacao:';
 return new Promise((resolve,reject)=>{const keys=[],request=storage.transaction('vaults').objectStore('vaults').openKeyCursor();request.onsuccess=()=>{const c=request.result;if(!c)return resolve(keys.sort().reverse());if(typeof c.key==='string'&&c.key.startsWith(prefix))keys.push(c.key.slice(vaultNamespace.length+1));c.continue();};request.onerror=()=>reject(Error('Não foi possível listar as cópias locais.'));});
}
async function decryptRecovery(blob,password){
 if(!blob||!Array.isArray(blob.salt)||!Array.isArray(blob.iv)||!Array.isArray(blob.cipher))throw Error('Cópia local inválida.');
 try{const oldKey=await derive(password,new Uint8Array(blob.salt));return JSON.parse(dec.decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:new Uint8Array(blob.iv)},oldKey,new Uint8Array(blob.cipher))));}
 catch{throw Error('Não foi possível abrir essa cópia com a senha informada. Nenhum dado foi alterado.');}
}
async function importRecovery(archive,old,owner){
 guard();if(vault.user.id!==owner)throw Error('Entre novamente na conta correta.');
 const state=await api('state');guard();if(state.user.id!==owner||vault.user.id!==owner)throw Error('A sessão pertence a outra conta.');
 const target=vault,added=recoveryPlan(old,target,state.records,archive),queue=target.queue,ledger=target.recoveredArchives;
 target.queue=[...queue,...added];target.recoveredArchives=[...(ledger||[]),archive];
 try{await save();}catch(e){target.queue=queue;if(ledger===undefined)delete target.recoveredArchives;else target.recoveredArchives=ledger;throw Error('Não foi possível gravar a recuperação. As cópias anteriores foram mantidas.');}
 return added.length;
}
async function openRecovery(){
 if(busy)return;
 try{guard();}catch(e){message(e.message);return;}
 const owner=vault.user.id,name=vault.user.name;
 let archives;try{archives=await recoveryArchives(name);}catch(e){message(e.message);return;}
 if(!vault||vault.user.id!==owner)return;
 archives=archives.filter(a=>!(vault.recoveredArchives||[]).includes(a));
 if(!archives.length){message('Não há cópias antigas ainda não recuperadas para esta conta neste navegador.');return;}
 const dialog=document.createElement('dialog');dialog.dataset.accessDialog='1';
 dialog.innerHTML='<form><h2>Recuperar pendências da senha antiga</h2><p>A senha antiga será usada somente neste navegador. Os dados atuais serão mantidos. Nada será enviado automaticamente ao servidor.</p><label>Cópia preservada<select name="archive"></select></label><label>Senha que protegia essa cópia<input name="oldPassword" type="password" required maxlength="200" autocomplete="off"></label><p role="status" aria-live="polite"></p><button type="submit">Conferir cópia</button> <button type="button" data-import hidden>Recuperar para a fila</button> <button type="button" data-cancel>Cancelar</button></form>';
 const form=dialog.querySelector('form'),select=form.elements.archive,password=form.elements.oldPassword,status=form.querySelector('[role=status]'),submit=form.querySelector('[type=submit]'),confirm=form.querySelector('[data-import]'),cancel=form.querySelector('[data-cancel]');
 for(const archive of archives){const option=document.createElement('option');option.value=archive;const timestamp=Number(archive.slice((name+':recuperacao:').length).split(':')[0]);option.textContent=Number.isFinite(timestamp)?new Date(timestamp).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})+' (Brasília)':archive;select.append(option);}
 let prepared=null;
 const reset=()=>{prepared=null;confirm.hidden=true;};select.onchange=reset;password.oninput=reset;
 const close=()=>{if(busy)return;prepared=null;password.value='';dialog.remove();};cancel.onclick=close;dialog.oncancel=e=>{e.preventDefault();close();};
 const disable=value=>{submit.disabled=confirm.disabled=cancel.disabled=select.disabled=value;};
 form.onsubmit=async e=>{
  e.preventDefault();if(busy)return;busy=true;disable(true);reset();
  try{guard();if(vault.user.id!==owner)throw Error('Entre novamente na conta correta.');const archive=select.value,blob=await getVault(archive),old=await decryptRecovery(blob,password.value);password.value='';
   const state=await api('state');guard();if(vault.user.id!==owner||state.user.id!==owner)throw Error('A sessão pertence a outra conta.');
   const added=recoveryPlan(old,vault,state.records,archive);prepared={archive,old};status.textContent=old.queue.length+' operação(ões) na cópia; '+added.length+' será(ão) adicionada(s) à fila atual. A confirmação mantém a cópia antiga e não sincroniza.';confirm.hidden=false;
  }catch(err){status.textContent=err.message;}finally{password.value='';busy=false;disable(false);}
 };
 confirm.onclick=async()=>{if(busy||!prepared)return;busy=true;disable(true);
  try{const count=await importRecovery(prepared.archive,prepared.old,owner);prepared=null;dialog.remove();render();message(count+' pendência(s) recuperada(s). Confira a fila antes de sincronizar. A cópia antiga foi mantida.');}
  catch(err){status.textContent=err.message;}finally{busy=false;disable(false);}
 };
 document.body.append(dialog);dialog.showModal();
}
const recoveryButton=document.createElement('button');recoveryButton.type='button';recoveryButton.className='secondary';recoveryButton.textContent='Recuperar pendências da senha antiga';recoveryButton.onclick=openRecovery;
$('queue').parentElement.insertBefore(recoveryButton,$('queue'));
