const {readFileSync}=require('node:fs');
const {runInNewContext}=require('node:vm');
const assert=require('node:assert/strict');
const source=readFileSync('public/app.js','utf8');
const handler=source.split(/\r?\n/).find(line=>line.startsWith("document.addEventListener('change',"));
assert.ok(handler,'change handler not found');
let onChange;
const state={teachers:[{name:''},{name:'Cô Lan'}],classes:[{name:''}],assignments:[{teacher:'',className:''},{teacher:'Cô Lan',className:'9/1'}]};
let warning='';runInNewContext(handler,{state,ScheduleLogic:require('../public/schedule-logic.js'),document:{addEventListener:(_,fn)=>onChange=fn},save(){},renderData(){},alert(message){warning=message}});
onChange({target:{dataset:{kind:'teachers',index:'0',field:'name'},value:'Cô Mai'}});
assert.equal(state.assignments[0].teacher,'');
onChange({target:{dataset:{kind:'teachers',index:'1',field:'name'},value:'Cô Lan Anh'}});
assert.equal(state.assignments[1].teacher,'Cô Lan Anh');
onChange({target:{dataset:{kind:'classes',index:'0',field:'name'},value:'9/2'}});
assert.equal(state.assignments[0].className,'');
const duplicate={dataset:{kind:'teachers',index:'0',field:'name'},value:'  CÔ   LAN ANH  '};onChange({target:duplicate});assert.equal(state.teachers[0].name,'Cô Mai');assert.equal(duplicate.value,'Cô Mai');assert.match(warning,/đã có/);
console.log('Empty assignments stay unassigned; existing teacher renames propagate.');

state.assignments[0].periods=2;
for(const value of ['2.5','0','31','']){
  const input={dataset:{kind:'assignments',index:'0',field:'periods'},value};
  onChange({target:input});assert.equal(state.assignments[0].periods,2);assert.equal(input.value,2);assert.match(warning,/số nguyên/);
}
onChange({target:{dataset:{kind:'assignments',index:'0',field:'periods'},value:'3'}});assert.equal(state.assignments[0].periods,3);
