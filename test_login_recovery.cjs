const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('web/app.js','utf8');
const login=src.slice(src.indexOf('async function login(offline)'),src.indexOf("$('loginForm').onsubmit"));
async function test(valid){
 const writes=[],messages=[],blob={cipher:[1,2,3]},elements={username:{value:'teste'},password:{value:'NovaSenhaFicticia123!'},login:{},workspace:{}};
 const ctx={vault:null,key:null,salt:null,current:null,lastActivity:0,vaultNamespace:'',Date,localStorage:{setItem(){}},crypto:{subtle:{},getRandomValues:a=>a,randomUUID:()=> 'unique'},Uint8Array,
 $:id=>elements[id],unlock:async()=>{throw Error('cofre antigo');},getVault:async()=>blob,setVault:async(k,v)=>writes.push([k,v]),
 api:async(path)=>{if(path==='setup')return {installation:'test'};if(path==='login'&&!valid)throw Error('Credencial inválida');if(path==='state')return {user:{id:'u',name:'teste'},records:{pacientes:[]}};},
 derive:async()=> 'key',save:async()=>writes.push(['save']),installationStatus(){},render(){},message:m=>messages.push(m)};
 vm.createContext(ctx);vm.runInContext(login,ctx);await ctx.login(false);
 if(valid){assert(writes[0][0].startsWith('teste:recuperacao:'));assert.strictEqual(writes[0][1],blob);assert.equal(writes[1][0],'save');assert(messages[0].includes('preservada'));}
 else{assert.equal(writes.length,0);assert.equal(ctx.vault,null);}
}
(async()=>{await test(true);await test(false);console.log('OK: cofre anterior preservado antes da nova gravação; senha inválida não altera armazenamento.');})();

