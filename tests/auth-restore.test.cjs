const {readFileSync}=require('node:fs');
const {runInNewContext}=require('node:vm');
const assert=require('node:assert/strict');
const code=readFileSync('public/auth.js','utf8');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function setup(){
  const classes=new Set(['auth-loading']);
  const elements=new Map();
  const get=selector=>{if(!elements.has(selector))elements.set(selector,{value:'',hidden:false,textContent:'',innerHTML:'',disabled:false});return elements.get(selector)};
  let resolveFetch,fetchArgs;const request=new Promise(resolve=>resolveFetch=resolve);
  const context={activeUser:null,storageReady:false,state:{},saveQueue:Promise.resolve(),defaults:()=>({}),dirtyKey:()=>'',localStorage:{getItem:()=>null},confirm:()=>true,
    $:get,window:{addEventListener(){}},document:{body:{classList:{add:(...names)=>names.forEach(x=>classes.add(x)),remove:(...names)=>names.forEach(x=>classes.delete(x))}},querySelectorAll:()=>[],addEventListener(){},hidden:false},
    fetch:(...args)=>{fetchArgs=args;return request},setInterval(){},storageStatus(){},hideSyncConflict(){},backupBox:{hidden:false}};
  context.init=async (user,preloaded)=>{context.activeUser=user;context.loaded=preloaded};
  runInNewContext(code,context);
  return {context,classes,get,resolveFetch,getFetch:()=>fetchArgs};
}
(async()=>{
  let h=setup();assert(h.classes.has('auth-loading'));assert(!h.classes.has('authenticated'));assert.equal(h.getFetch()[0],'/api/auth/bootstrap');assert.equal(h.getFetch()[1].credentials,'same-origin');
  h.resolveFetch({ok:true,status:200,json:async()=>({id:7,username:'giaovien',state:{term:'HK1'}})});await tick();await tick();
  assert(h.classes.has('authenticated'));assert(!h.classes.has('auth-loading'));assert.equal(h.get('#profile-name').textContent,'giaovien');assert.equal(h.context.loaded.term,'HK1');
  h=setup();h.resolveFetch({ok:false,status:401});await tick();await tick();assert(!h.classes.has('auth-loading'));assert(!h.classes.has('authenticated'));assert.equal(h.get('#auth-retry').hidden,true);
  h=setup();h.resolveFetch({ok:false,status:503});await tick();await tick();assert(!h.classes.has('auth-loading'));assert.equal(h.get('#auth-retry').hidden,false);assert.match(h.get('#auth-message').textContent,/khôi phục/);
  h=setup();h.resolveFetch({ok:true,status:200,json:async()=>({id:7,username:'giaovien'})});await tick();await tick();h.context.window.sessionExpired();assert(!h.classes.has('authenticated'));assert.match(h.get('#auth-message').textContent,/thiết bị khác/);
  console.log('Reload restores existing session; missing sessions and temporary errors are distinguished.');
})().catch(err=>{console.error(err);process.exitCode=1});
