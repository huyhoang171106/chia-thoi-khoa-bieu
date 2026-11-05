const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const box={after(){},addEventListener(){},querySelector:()=>({textContent:''})};
const context={document:{createElement:()=>box,querySelector:()=>({after(){}})}};
vm.createContext(context);vm.runInContext(fs.readFileSync('public/sync-recovery.js','utf8'),context);
assert.equal(context.sameState({b:[{x:1,y:2}],a:3},{a:3,b:[{y:2,x:1}]}),true);
assert.equal(context.sameState({schedule:[1,2]},{schedule:[2,1]}),false);
assert.equal(context.sameState({teachers:[{name:'Lan'}]},{teachers:[{name:'Minh'}]}),false);
console.log('Sync comparison preserves array order and detects differences.');
