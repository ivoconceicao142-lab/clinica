// Atualize a versão ao alterar o conjunto de arquivos da interface.
const CACHE='clinica-shell-offline-20261112-2';
const FILES=['/','/app.js','/v2.js','/modules.js','/style.css','/manifest.json'];
self.addEventListener('install',event=>event.waitUntil((async()=>{
 const cache=await caches.open(CACHE);
 // Só ativa se todos os arquivos necessários estiverem disponíveis.
 await cache.addAll(FILES.map(path=>new Request(path,{cache:'reload'})));
 await self.skipWaiting();
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{
 for(const name of await caches.keys()){
  if(name.startsWith('clinica-shell-')&&name!==CACHE)await caches.delete(name);
 }
 await self.clients.claim();
})()));
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 if(event.request.method!=='GET'||url.origin!==self.location.origin||!FILES.includes(url.pathname))return;
 event.respondWith((async()=>{
  const cache=await caches.open(CACHE);
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),5000);
  try{
   const response=await fetch(event.request,{cache:'no-store',signal:controller.signal});
   if(!response.ok)throw new Error('Arquivo indisponível');
   // A atualização online também fica disponível para a próxima abertura offline.
   try{await cache.put(url.pathname,response.clone());}catch{/* Mantém a resposta online se o armazenamento estiver cheio. */}
   return response;
  }catch(error){
   const saved=await cache.match(url.pathname);
   if(saved)return saved;
   return new Response('Arquivo offline indisponível. Reconecte para atualizar a clínica.',{status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}});
  }finally{clearTimeout(timeout);}
 })());
});
