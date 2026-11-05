const assert=require('node:assert/strict');
const logic=require('../public/schedule-logic.js');
assert.deepEqual(logic.sessionRange({sessionRule:'6'}),{min:6,max:6});assert.deepEqual(logic.sessionRange({}),{min:4,max:5});
const initial={classes:[{name:'6/1',shift:'morning'},{name:'6/2',shift:'morning'}],teachers:[{name:'Lan',maxSessions:3},{name:'Minh',maxSessions:3}],subjects:[],events:[],assignments:[{className:'6/1',subject:'Toán',periods:3},{className:'6/1',subject:'Văn',periods:3},{className:'6/2',subject:'Anh',periods:3}],schedule:[
  {className:'6/1',shift:'morning',day:0,period:1,subject:'Toán',teacher:'Lan'},
  {className:'6/1',shift:'morning',day:0,period:2,subject:'Văn',teacher:'Minh'},
  {className:'6/2',shift:'morning',day:0,period:3,subject:'Anh',teacher:'Lan'},
  {className:'6/1',shift:'morning',day:1,period:1,subject:'Chào cờ',teacher:''}
]};
assert.equal(logic.validate(initial.schedule,initial.teachers,initial.assignments),'');
assert.equal(logic.versionSignature(JSON.stringify([initial.classes,initial.teachers,[{grade:'6',name:'Văn'}],initial.assignments,initial.events])),logic.inputSignature(initial));
assert.match(logic.move(initial,'6/1',0,1,0,3).error,/trống|thời điểm/);
assert.match(logic.move(initial,'6/1',1,1,1,2).error,/cố định/);
assert.match(logic.move(initial,'6/1',0,1,0,2).error||'',/^$/);
const moved=logic.move(initial,'6/1',0,1,0,2).schedule;assert.equal(moved.find(x=>x.className==='6/1'&&x.day===0&&x.period===2).subject,'Toán');assert.equal(initial.schedule[0].period,1);
const constrained=structuredClone(initial);constrained.schedule.push({className:'6/2',shift:'morning',day:0,period:4,subject:'Văn',teacher:'Minh'});for(let day=1;day<=4;day++)constrained.schedule.push({className:'6/2',shift:'morning',day,period:1,subject:'Văn',teacher:'Minh'});constrained.schedule.push({className:'6/2',shift:'afternoon',day:0,period:1,subject:'Văn',teacher:'Minh'});assert.match(logic.validate(constrained.schedule,constrained.teachers,constrained.assignments,{partial:true}),/vượt/);
const gap={teachers:[{name:'Lan',maxSessions:6}],assignments:[{className:'9/1',subject:'Sử',periods:2}],schedule:[{className:'9/1',shift:'morning',day:0,period:1,subject:'Sử',teacher:'Lan'},{className:'9/1',shift:'morning',day:3,period:1,subject:'Sử',teacher:'Lan'}]};
assert.match(logic.move(gap,'9/1',3,1,1,1).error,/cách nhau/);
const gapTeacher=[{className:'6/1',shift:'morning',day:0,period:1,subject:'Toán',teacher:'Lan'},{className:'6/2',shift:'morning',day:0,period:3,subject:'Văn',teacher:'Lan'}];
const gapAssignments=[{className:'6/1',subject:'Toán',periods:1},{className:'6/2',subject:'Văn',periods:1}],gapTeachers=[{name:'Lan',sessionRule:'1'}];
assert.equal(logic.validate(gapTeacher,gapTeachers,gapAssignments),'');
gapTeacher[1].period=4;assert.match(logic.validate(gapTeacher,gapTeachers,gapAssignments),/hơn 1 tiết trống/);
assert.equal(logic.validate(gapTeacher,gapTeachers,gapAssignments,{partial:true}),'');
gapTeacher[1].shift='afternoon';gapTeachers[0].sessionRule='2';assert.equal(logic.validate(gapTeacher,gapTeachers,gapAssignments),'');
function two(subject,day,period,count=2){const records=[{className:'9/1',shift:'morning',day:0,period:1,subject,teacher:'Lan'},{className:'9/1',shift:'morning',day,period,subject,teacher:'Lan'}];return logic.validate(records,[{name:'Lan',sessionRule:day===0?'1':'2'}],[{className:'9/1',subject,periods:count}],{partial:true})}
assert.equal(two('Toán',1,1),'');assert.equal(two('Tiếng Anh',1,1),'');assert.equal(two('Ngữ văn',0,2),'');
assert.equal(two('Lịch sử',2,1),'');
assert.match(two('Lịch sử',1,1),/cách nhau/);assert.match(two('Toán',0,2),/Chỉ môn Văn/);assert.match(two('Tiếng Anh',0,2,4),/1 tiết Anh/);
assert.equal(two('Toán',0,3),'');assert.match(two('Anh',0,3),/1 tiết Anh/);
const threeMath=[1,3,5].map(period=>({className:'9/1',shift:'morning',day:0,period,subject:'Toán',teacher:'Lan'}));assert.match(logic.validate(threeMath,[{name:'Lan',sessionRule:'1'}],[{className:'9/1',subject:'Toán',periods:3}],{partial:true}),/2 tiết Toán/);
const mixed=[{className:'9/1',shift:'morning',day:0,period:1,subject:'Toán',teacher:'Lan'},{className:'9/1',shift:'morning',day:0,period:2,subject:'Anh',teacher:'Minh'}];
assert.equal(logic.validate(mixed,[{name:'Lan'},{name:'Minh'}],[],{partial:true}),'');
mixed[0].subject='Tiếng Anh';assert.match(logic.validate(mixed,[{name:'Lan'},{name:'Minh'}],[],{partial:true}),/1 tiết Anh/);
const triple=[1,2,3].map(period=>({className:'9/1',shift:'morning',day:0,period,subject:'Văn',teacher:'Lan'}));assert.match(logic.validate(triple,[{name:'Lan',sessionRule:'1'}],[{className:'9/1',subject:'Văn',periods:3}],{partial:true}),/tối đa 2 tiết/);
const shared=[{className:'9/1',shift:'morning',day:0,period:1,subject:'Toán',teacher:'Lan'},{className:'9/1',shift:'morning',day:0,period:2,subject:'Toán',teacher:'Minh'}];assert.match(logic.validate(shared,[{name:'Lan',sessionRule:'1'},{name:'Minh',sessionRule:'1'}],[{className:'9/1',subject:'Toán',teacher:'Lan',periods:1},{className:'9/1',subject:'Toán',teacher:'Minh',periods:1}],{partial:true}),/Chỉ môn Văn/);
const old={schedule:[{className:'9/1',day:5,teacher:'Lan',locked:true},{className:'9/1',day:4,teacher:'Lan'}],events:[{name:'Sinh hoạt',day:5},{name:'Chào cờ',day:0}],assignments:[{className:'9/1',teacher:'Lan',subject:'Toán',periods:2}]};const migrated=logic.trimSaturday(old);assert.equal(migrated.removedLessons,1);assert.equal(migrated.removedEvents,1);assert.equal(migrated.state.schedule.length,1);assert.equal(migrated.state.assignments.length,1);assert.equal(old.schedule.length,2);assert.match(logic.validate([{className:'9/1',shift:'morning',day:5,period:1,subject:'Toán',teacher:'Lan'}],[{name:'Lan'}],old.assignments,{partial:true}),/thứ Sáu/);
console.log('Moves, swaps, teacher conflicts, fixed events, gaps and subject spacing passed.');
