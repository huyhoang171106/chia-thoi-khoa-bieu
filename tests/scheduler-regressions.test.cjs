const assert=require('node:assert/strict');
const logic=require('../public/schedule-logic.js');
const board=require('../public/board-logic.js');
const assignment=(subject,periods=1)=>({className:'9/1',teacher:'Lan',subject,periods});
const lesson=(subject,day,period)=>({...assignment(subject),shift:'morning',day,period});

for(const alias of ['Toan','Toa\u0301n',' TOÁN ']){
  const assignments=[assignment('Toán'),assignment(alias)],teachers=[{name:'Lan',sessionRule:'1'}];
  assert.match(logic.validate([lesson('Toán',0,1),lesson(alias,0,2)],teachers,assignments),/Chỉ môn Văn/);
  const spaced=[lesson('Toán',0,1),{...lesson('Sinh hoạt',0,2),teacher:''},lesson(alias,0,3)];
  assert.equal(logic.validate(spaced,teachers,assignments),'');
}
const state={classes:[{name:'9/1',shift:'morning'}],teachers:[{name:'Lan',sessionRule:'2'}],events:[],
  assignments:['A','B','C','D'].map(s=>assignment(s)),
  schedule:[lesson('A',0,1),lesson('B',0,2),lesson('C',2,1),lesson('D',2,2)]};
assert.equal(logic.validate(state.schedule,state.teachers,state.assignments),'');
assert.match(logic.move(state,'9/1',2,1,0,3,'morning').error,/ít nhất 2 tiết/);
const merged=state.schedule.map((x,i)=>({...x,day:0,period:i+1}));
assert.match(logic.validate(merged,state.teachers,state.assignments),/chưa đủ số buổi/);
assert.equal(logic.validate(merged,state.teachers,state.assignments,{partial:true}),'');
assert.match(logic.validate([],state.teachers,state.assignments),/chưa đủ số buổi/);
assert.equal(logic.validate([], [{name:'Chưa phân công'}], []),'');
state.schedule=merged.slice(0,3);
assert.match(board.place(state,{kind:'pool',index:3},{className:'9/1',day:0,period:4},logic).error,/chưa đủ số buổi/);
state.schedule=[lesson('A',0,1),lesson('B',0,2),lesson('C',2,1)];
assert.ok(board.place(state,{kind:'pool',index:3},{className:'9/1',day:2,period:2},logic).schedule);
for(const periods of [2.5,'2.5',0,31,true,null,NaN,Infinity]){
  assert.match(logic.validate([],state.teachers,[assignment('Văn',periods)],{partial:true}),/số nguyên/);
}
console.log('Subject normalization, complete-session rules and integer periods passed.');

const unfinished={...state,schedule:[lesson('A',0,1)]};
assert.ok(logic.move(unfinished,'9/1',0,1,2,1,'morning',{partial:true}).schedule);
