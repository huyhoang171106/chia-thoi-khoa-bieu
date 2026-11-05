(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ScheduleLogic=api})(globalThis,function(){
  function inputSignature(state){return JSON.stringify([state.classes,state.teachers,state.assignments,state.events])}
  function versionSignature(signature){try{const parts=JSON.parse(signature);if(Array.isArray(parts)&&parts.length===5){parts.splice(2,1);return JSON.stringify(parts)}}catch{}return signature}
  function trimSaturday(value){const state={...value};const originalSchedule=Array.isArray(value.schedule)?value.schedule:[],originalEvents=Array.isArray(value.events)?value.events:[];const removedLessons=originalSchedule.filter(x=>Number(x.day)===5&&x.teacher).length,removedEvents=originalEvents.filter(x=>Number(x.day)===5).length;state.schedule=originalSchedule.filter(x=>Number(x.day)!==5);state.events=originalEvents.filter(x=>Number(x.day)!==5);if(removedLessons||removedEvents)state.resultMessage='Đã đưa các tiết thứ Bảy về danh sách chưa xếp; hãy kiểm tra lại hoạt động cố định và tạo lịch mới.';return {state,removedLessons,removedEvents,changed:state.schedule.length!==originalSchedule.length||state.events.length!==originalEvents.length};}
  function teacherKey(name){return String(name??'').trim().replace(/\s+/gu,' ').normalize('NFC').toLocaleLowerCase('vi')}
  function sessionRange(teacher){const rule=String(teacher?.sessionRule||'standard');return /^[1-6]$/.test(rule)?{min:Number(rule),max:Number(rule)}:{min:4,max:5}}
  function teacherUnavailable(teacher,shift,day,period){const rule=String(teacher?.offRule||'standard').split(':');return rule[0]==='first'&&period===1||rule[0]==='day'&&Number(rule[1])===day||rule[0]==='session'&&Number(rule[1])===day&&rule[2]===shift}
  function subjectKey(subject){return String(subject||'').toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').replace(/[^a-z0-9]/g,'')}
  function extraKind(subject){const name=subjectKey(subject);return name==='hoatdongtrainghiem'?1:name==='theduc'?2:0}
  function literature(subject){return ['van','nguvan'].includes(subjectKey(subject))}
  function subjectGroup(subject){return literature(subject)?'van':String(subject||'').toLocaleLowerCase('vi')}
  function flexibleDays(subject){return ['toan','anh','tienganh'].includes(subjectKey(subject))}
  function literatureError(items,className,total,partial){
    const groups=new Map();for(const x of items){const key=JSON.stringify([x.shift,x.day]),group=groups.get(key)||[];group.push(x.period);groups.set(key,group)}
    let singles=0;for(const [key,periods] of groups){periods.sort((a,b)=>a-b);if(periods.length>2)return `Môn Văn của lớp ${className} chỉ được học tối đa 2 tiết trong một buổi.`;if(periods.length===2&&periods[1]-periods[0]!==1)return `Hai tiết Văn của lớp ${className} trong cùng buổi phải liền nhau.`;if(periods.length===1)singles++;}
    if(!partial&&total>0&&singles!==total%2)return `Các tiết Văn của lớp ${className} phải ghép thành từng cặp liền nhau; chỉ được một tiết lẻ nếu số tiết tuần là số lẻ.`;
    return '';
  }
  function literatureRuleIssue(schedule,assignments,partial=false){
    const classes=new Map();for(const x of schedule||[]){if(!x.teacher||!literature(x.subject))continue;const items=classes.get(x.className)||[];items.push(x);classes.set(x.className,items)}
    for(const [className,items] of classes){const total=(assignments||[]).filter(a=>a.className===className&&literature(a.subject)).reduce((sum,a)=>sum+Number(a.periods||0),0),error=literatureError(items,className,total,partial);if(error)return error}return '';
  }
  function validate(schedule,teachers,assignments,options={}){
    const occupied=new Set(), teacherSlots=new Set(), loads=new Map(), teacherPeriods=new Map(), classDays=new Map(), subjects=new Map(),extra=new Map();
    for(const x of schedule){
      if(!Number.isInteger(x.day)||x.day<0||x.day>4||!Number.isInteger(x.period)||x.period<1||x.period>5)return 'Chỉ xếp lịch từ thứ Hai đến thứ Sáu, tiết 1–5.';
      const cell=JSON.stringify([x.className,x.shift,x.day,x.period]);if(occupied.has(cell))return `Lớp ${x.className} bị trùng tiết.`;occupied.add(cell);
      const dayKey=JSON.stringify([x.className,x.shift,x.day]),periods=classDays.get(dayKey)||[];periods.push(x.period);classDays.set(dayKey,periods);
      if(!x.teacher)continue;
      if(teacherUnavailable(teachers.find(t=>t.name===x.teacher),x.shift,x.day,x.period))return `Giáo viên ${x.teacher} đã chọn nghỉ vào thời gian này.`;
      const slot=`${x.teacher}|${x.shift}|${x.day}|${x.period}`;if(teacherSlots.has(slot))return `Giáo viên ${x.teacher} đã có tiết dạy vào thời điểm đó.`;teacherSlots.add(slot);
      const sessions=loads.get(x.teacher)||new Set();sessions.add(`${x.shift}|${x.day}`);loads.set(x.teacher,sessions);
      const teachingKey=JSON.stringify([x.teacher,x.shift,x.day]),teaching=teacherPeriods.get(teachingKey)||[];teaching.push(x.period);teacherPeriods.set(teachingKey,teaching);
      const kind=extraKind(x.subject);if(kind){const items=extra.get(x.className)||[];items.push(x);extra.set(x.className,items);}else{const subjectKey=`${x.className}|${subjectGroup(x.subject)}`,subjectDays=subjects.get(subjectKey)||[];subjectDays.push(x);subjects.set(subjectKey,subjectDays);}
    }
    const limitedSessions=new Map();
    for(const x of schedule){if(!x.teacher)continue;const subject=subjectKey(x.subject),kind=subject==='toan'?'toan':['anh','tienganh'].includes(subject)?'anh':'';if(!kind)continue;const key=JSON.stringify([x.className,x.shift,x.day,kind]),count=(limitedSessions.get(key)||0)+1;if(count>(kind==='toan'?2:1))return `Lớp ${x.className} chỉ được học tối đa ${kind==='toan'?'2 tiết Toán':'1 tiết Anh'} trong mỗi buổi.`;limitedSessions.set(key,count);}
    for(const [teacher,sessions] of loads){const person=teachers.find(t=>t.name===teacher),max=sessionRange(person).max;if(!person||sessions.size>max)return `Giáo viên ${teacher} vượt số buổi dạy đã chọn (${max} buổi/tuần).`;}
    if(!options.partial)for(const [key,periods] of teacherPeriods){periods.sort((a,b)=>a-b);for(let i=1;i<periods.length;i++)if(periods[i]-periods[i-1]>2)return `Giáo viên ${JSON.parse(key)[0]} có hơn 1 tiết trống giữa hai tiết dạy trong cùng buổi.`;}
    if(!options.partial)for(const [key,periods] of classDays){periods.sort((a,b)=>a-b);if(periods[periods.length-1]-periods[0]+1!==periods.length)return `Lớp ${JSON.parse(key)[0]} sẽ có tiết trống giữa buổi.`;}
    for(const [className,items] of extra){const first=items[0];if(items.some(x=>x.shift!==first.shift||x.day!==first.day||x.period>4))return `Hai môn trái buổi của lớp ${className} phải cùng buổi, từ tiết 1 đến 4.`;const fits=[1,2].some(start=>items.every(x=>extraKind(x.subject)===(x.period<=2?start:3-start)));if(!fits)return `Mỗi môn trái buổi của lớp ${className} phải chiếm một cặp tiết liên tục: 1–2 hoặc 3–4.`;if(!options.partial&&items.length!==4)return `Lớp ${className} cần đủ 4 tiết trái buổi.`;}
    for(const [key,subjectDays] of subjects){
      const separator=key.indexOf('|'),className=key.slice(0,separator),subject=key.slice(separator+1);
      const count=assignments.filter(a=>a.className===className&&subjectGroup(a.subject)===subject).reduce((sum,a)=>sum+Number(a.periods),0);
      if(literature(subject)){const error=literatureError(subjectDays,className,count,!!options.partial);if(error)return error;continue}
      for(let i=0;i<subjectDays.length;i++)for(let j=i+1;j<subjectDays.length;j++){
        const a=subjectDays[i],b=subjectDays[j],adjacent=a.shift===b.shift&&a.day===b.day&&Math.abs(a.period-b.period)===1;
        if(adjacent)return `Chỉ môn Văn được học tiết đôi trong buổi chính; lớp ${className} đang có 2 tiết ${subject} liền nhau.`;
        if(count<3&&!flexibleDays(subject)){const single=a.teacher===b.teacher&&a.day===b.day&&a.shift===b.shift&&sessionRange(teachers.find(t=>t.name===a.teacher)).max===1;if(!single&&Math.abs(a.day-b.day)<2)return `Môn ${subject} của lớp ${className} cần cách nhau ít nhất 1 ngày ở giữa.`;}
      }
    }
    return '';
  }
  function move(state,className,fromDay,fromPeriod,toDay,toPeriod,shift){
    const schedule=state.schedule.map(x=>({...x}));const source=schedule.find(x=>x.className===className&&(!shift||x.shift===shift)&&x.day===fromDay&&x.period===fromPeriod);const target=schedule.find(x=>x.className===className&&(!shift||x.shift===shift)&&x.day===toDay&&x.period===toPeriod);
    if(!source)return {error:'Hãy chọn một tiết học để di chuyển.'};if(!source.teacher||target&&!target.teacher)return {error:'Không thể di chuyển hoạt động cố định. Hãy sửa trong Thiết lập tuần học.'};if(source.locked||target?.locked)return {error:'Hãy mở khóa tiết trước khi di chuyển.'};
    if(fromDay===toDay&&fromPeriod===toPeriod)return {error:'Hãy chọn một ô khác.'};
    if(target){target.day=fromDay;target.period=fromPeriod}source.day=toDay;source.period=toPeriod;
    const error=validate(schedule,state.teachers,state.assignments);return error?{error}:{schedule};
  }
  return {inputSignature,versionSignature,validate,move,extraKind,teacherKey,sessionRange,trimSaturday,literatureRuleIssue};
});
