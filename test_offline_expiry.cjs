const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('web/app.js','utf8');
const expiry=src.slice(src.indexOf('function accessExpired('),src.indexOf('function guard('));
const check=src.slice(src.indexOf('function checkAccessDeadline('),src.indexOf("window.addEventListener('online'"));
for(const scenario of [
 {label:'active valid',age:1000,idle:0,lock:false},
 {label:'active at eight hours',age:8*3600000,idle:0,lock:true},
 {label:'active after nine hours',age:9*3600000,idle:0,lock:true},
 {label:'clock rollback',age:-1,idle:0,lock:true},
 {label:'invalid timestamp',invalid:true,age:0,idle:0,lock:true},
 {label:'inactivity',age:3600000,idle:300000,lock:true}]){
 let now=100000000,locked=false,timer;const events={},queue=[{id:'pending-test'}];
 const ctx={vault:{verified:scenario.invalid?undefined:now-scenario.age,queue},lastActivity:now-scenario.idle,Date:{now:()=>now},Number,message(){},lockScreen(){locked=true;ctx.vault=null;},document:{addEventListener:(n,f)=>events[n]=f},window:{addEventListener:(n,f)=>events[n]=f},setInterval:f=>timer=f};
 vm.createContext(ctx);vm.runInContext(expiry+check,ctx);timer();assert.equal(locked,scenario.lock,scenario.label);assert.equal(queue.length,1);
 if(!scenario.lock){now+=9*3600000;events.focus();assert(locked,'focus after suspension');}
}
console.log('OK: expiration, continuous activity, inactivity, clock rollback, invalid time and focus; pending queue preserved.');
