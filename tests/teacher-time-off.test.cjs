const assert=require('node:assert/strict'), logic=require('../public/schedule-logic.js');
const lesson={className:'6/1',shift:'morning',day:1,period:1,subject:'Toán',teacher:'Lan'};
for(const rule of ['first','session:1:morning','day:1']) assert.match(logic.validate([lesson],[{name:'Lan',offRule:rule}],[],{partial:true}),/nghỉ/);
for(const rule of ['standard','session:1:afternoon','day:2']) assert.equal(logic.validate([lesson],[{name:'Lan',offRule:rule}],[],{partial:true}),'');
console.log('Manual teacher time off validation passed.');
