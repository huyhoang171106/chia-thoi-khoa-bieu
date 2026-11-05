(function(){
  const button=document.createElement('button');button.type='button';button.id='export-school';button.className='outline';button.textContent='↓ Xuất Excel toàn trường';
  document.querySelector('#export').after(button);
  button.addEventListener('click',async()=>{
    if(!state.schedule.length){alert('Hãy tạo hoặc xếp thời khóa biểu trước nha.');return}
    const notice=$('#notice');button.disabled=true;const label=button.textContent;button.textContent='Đang tạo file Excel…';
    try{
      const payload={term:state.term,classes:state.classes,events:state.events,schedule:state.schedule},remaining=BoardLogic.remaining(state).length;
      const response=await fetch('/api/export-school-xlsx',{method:'POST',headers:{'Content-Type':'application/json','X-LT-User':String(activeUser.id)},body:JSON.stringify(payload)});
      if(response.status===401){window.sessionExpired();return}
      if(!response.ok){let data;try{data=await response.json()}catch{}throw Error(data?.error||'Không tạo được file Excel. Hãy khởi động lại máy chủ rồi thử lại.')}
      const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='thoi-khoa-bieu-toan-truong.xlsx';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      notice.className='notice';notice.textContent=remaining?`Đã xuất lịch tại thời điểm bấm nút; còn ${remaining} tiết chưa xếp nên chưa có trong file.`:'Đã xuất Excel toàn trường, mỗi khối một trang tính.';notice.hidden=false;
    }catch(err){notice.className='notice error';notice.textContent=err.message||'Không thể xuất Excel.';notice.hidden=false}
    finally{button.disabled=false;button.textContent=label}
  });
})();
