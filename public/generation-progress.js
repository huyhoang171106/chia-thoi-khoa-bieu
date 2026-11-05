(function(){
  const card=document.querySelector('.generate-card');
  const box=document.createElement('div');
  box.className='generation-progress';box.hidden=true;
  box.innerHTML='<div class="generation-progress-head"><strong id="generation-progress-label">Đang chuẩn bị dữ liệu…</strong><span id="generation-progress-count"></span></div><progress id="generation-progress-bar" aria-labelledby="generation-progress-label"></progress><p>Hệ thống tiếp tục thử cho đến khi tìm được lịch. Không thể dự đoán thời gian hoàn tất.</p><button type="button" class="outline" id="generation-cancel">Dừng xếp lịch</button>';
  card.after(box);
  const label=box.querySelector('#generation-progress-label'),count=box.querySelector('#generation-progress-count'),bar=box.querySelector('progress'),cancel=box.querySelector('#generation-cancel'),description=box.querySelector('p');let controller=null;
  cancel.addEventListener('click',()=>{if(controller){cancel.disabled=true;label.textContent='Đang dừng xếp lịch…';controller.abort();}});
  window.generationProgress={
    start(){controller=new AbortController();box.hidden=false;box.classList.remove('failed');bar.removeAttribute('value');cancel.hidden=false;cancel.disabled=false;cancel.textContent='Dừng xếp lịch';label.textContent='Đang kiểm tra dữ liệu…';count.textContent='';description.textContent='Hệ thống đang tìm lịch hoặc kiểm tra các quy định có thể thỏa cùng nhau. Không thể dự đoán thời gian hoàn tất.';},
    better(){label.textContent='Đã có lịch hợp lệ, đang làm cho lịch tốt hơn…';cancel.textContent='Dùng lịch hiện tại';description.textContent='Lịch sẽ ít buổi và ít tiết trống hơn nếu chờ thêm. Bấm "Dùng lịch hiện tại" để lấy ngay lịch tốt nhất đã tìm được.';},
    search(elapsed){bar.removeAttribute('value');if(cancel.textContent!=='Dùng lịch hiện tại')label.textContent='Đang tìm lịch theo các quy định…';count.textContent=`Đã chạy ${Math.max(0,Math.floor(elapsed))} giây`;},
    update(completed,total,unlimited){if(!Number.isInteger(completed)||completed<0)return;if(unlimited){bar.removeAttribute('value');count.textContent=`Đã thử ${completed} lượt`;}else{if(!Number.isInteger(total)||total<1||completed>total)return;bar.max=total;bar.value=completed;count.textContent=`${completed} / ${total} lần thử`;description.textContent='Máy chủ đang dùng phiên bản giới hạn số lượt thử. Hãy khởi động lại máy chủ để áp dụng bản mới.';}label.textContent='Đang thử các cách xếp lịch…';},
    finish(){controller=null;cancel.hidden=true;bar.max=1;bar.value=1;label.textContent='Đã xếp lịch xong';count.textContent='Hoàn tất';},
    fail(){controller=null;cancel.hidden=true;box.classList.add('failed');label.textContent='Chưa hoàn tất xếp lịch';count.textContent='';},
    stopped(){controller=null;cancel.hidden=true;bar.removeAttribute('value');label.textContent='Đã dừng xếp lịch';}
  };
  window.generateWithProgress=async function(state,userId){
    let best=null;
    try{
    const response=await fetch('/api/generate-stream',{method:'POST',headers:{'Content-Type':'application/json','X-LT-User':String(userId)},body:JSON.stringify(state),signal:controller?.signal});
    if(response.status===401){window.sessionExpired();throw Error('Phiên đăng nhập đã hết hạn.');}
    if(!response.ok){const data=await response.json();throw Error(data.error||'Không thể tạo lịch');}
    if(!(response.headers.get('content-type')||'').includes('application/x-ndjson')){label.textContent='Đang xếp lịch; máy chủ chưa hỗ trợ báo tiến độ.';description.textContent='Hãy khởi động lại máy chủ để áp dụng chế độ thử cho đến khi tìm được lịch.';return await response.json();}
    if(!response.body)throw Error('Không nhận được tiến độ xếp lịch.');
    const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',result;
    function processLine(line){if(!line.trim())return;const event=JSON.parse(line);if(event.type==='progress'){if(event.phase==='search')generationProgress.search(event.elapsed);else generationProgress.update(event.completed,event.total,event.unlimited);}else if(event.type==='error')throw Error(event.error||'Không thể tạo lịch');else if(event.type==='partial'){best=event.result;generationProgress.better();}else if(event.type==='result')result=event.result;}
    while(true){const {value,done}=await reader.read();buffer+=decoder.decode(value||new Uint8Array(),{stream:!done});const lines=buffer.split('\n');buffer=lines.pop();for(const line of lines)processLine(line);if(done)break;}
    processLine(buffer);if(!result)throw Error('Kết nối kết thúc trước khi nhận được kết quả xếp lịch.');return result;
    }catch(e){if(e.name==='AbortError'&&best)return {...best,message:best.message+' Đã dừng cải thiện sớm theo yêu cầu.'};throw e;}
  };
})();
