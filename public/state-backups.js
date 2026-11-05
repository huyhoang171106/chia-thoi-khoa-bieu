(function(root){
  function writeLocalState(storage,key,value){
    const old=storage.getItem(key);
    if(old&&old!==value){
      let parsed;try{parsed=JSON.parse(old)}catch{parsed=null}
      if(parsed&&typeof parsed==='object'){
        const backupKey=key+':backups';let backups=[];try{const existing=JSON.parse(storage.getItem(backupKey)||'[]');if(Array.isArray(existing))backups=existing}catch{}
        if(!backups.length||backups[0].data!==old){backups.unshift({savedAt:new Date().toISOString(),data:old});storage.setItem(backupKey,JSON.stringify(backups.slice(0,15)));}
      }
    }
    storage.setItem(key,value);
  }
  root.writeLocalState=writeLocalState;
})(globalThis);
