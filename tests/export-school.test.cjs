const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const state={term:'HK1',classes:[{name:'6/1',grade:'6',shift:'morning'}],events:[],assignments:[],schedule:[{className:'6/1',subject:'Toán',teacher:'Lan',shift:'morning',day:0,period:1}]};
const notice={},anchor={},button={addEventListener(_,fn){this.action=fn}},exportButton={after(el){assert.equal(el,button)}};
let sent,downloaded,blobUrlRevoked=false;
const document={querySelector(selector){assert.equal(selector,'#export');return exportButton},createElement(kind){return kind==='button'?button:anchor}};
anchor.click=()=>{downloaded=anchor.download};
const context={document,state,activeUser:{id:42},BoardLogic:{remaining:()=>[{}]},$:()=>notice,alert(){throw Error('Unexpected alert')},
  fetch:async(url,request)=>{sent={url,request};return {ok:true,blob:async()=>new Blob(['xlsx'])}},
  URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:()=>{blobUrlRevoked=true}},setTimeout:fn=>fn(),window:{sessionExpired(){throw Error('Unexpected expiration')}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('public/export-school.js','utf8'),context);
(async()=>{await button.action();assert.equal(sent.url,'/api/export-school-xlsx');assert.equal(sent.request.headers['X-LT-User'],'42');assert.deepEqual(JSON.parse(sent.request.body),{term:state.term,classes:state.classes,events:state.events,schedule:state.schedule});assert.equal(downloaded,'thoi-khoa-bieu-toan-truong.xlsx');assert.equal(blobUrlRevoked,true);assert.match(notice.textContent,/1 tiết chưa xếp/);assert.equal(button.disabled,false);console.log('Whole-school download uses current state and reports unplaced lessons.');})().catch(err=>{console.error(err);process.exitCode=1});
