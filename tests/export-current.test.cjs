const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const line=fs.readFileSync('public/app.js','utf8').split(/\r?\n/).find(x=>x.startsWith("$('#export').onclick="));assert.ok(line);
const state={schedule:[{className:'6/1',teacher:'Lan',shift:'morning',day:0,period:1,subject:'Toán'}, {className:'6/2',teacher:'Minh',shift:'morning',day:0,period:1,subject:'Văn'}]};
const elements={'#export':{},'#view-type':{value:'class'},'#view-name':{value:'6/1'}};let savedBlob;const anchor={click(){}};
const context={state,$:s=>elements[s],days:['Thứ Hai'],document:{createElement:()=>anchor},Blob,URL:{createObjectURL:b=>{savedBlob=b;return 'blob:test'},revokeObjectURL(){}},setTimeout(){},alert(){throw Error('Unexpected alert')}};
vm.createContext(context);vm.runInContext(line,context);elements['#export'].onclick();
(async()=>{const csv=await savedBlob.text();assert.match(csv,/6\/1/);assert.doesNotMatch(csv,/6\/2/);elements['#view-type'].value='teacher';elements['#view-name'].value='Minh';elements['#export'].onclick();const teacherCsv=await savedBlob.text();assert.match(teacherCsv,/6\/2/);assert.doesNotMatch(teacherCsv,/6\/1/);console.log('CSV export follows the selected class or teacher.');})().catch(err=>{console.error(err);process.exitCode=1});
