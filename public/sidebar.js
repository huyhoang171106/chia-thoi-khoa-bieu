(function(){
  const app=document.querySelector('.app'),sidebar=document.querySelector('.sidebar');
  sidebar.id='main-sidebar';
  const toggle=document.createElement('button');toggle.type='button';toggle.className='sidebar-toggle';toggle.setAttribute('aria-controls','main-sidebar');
  sidebar.insertBefore(toggle,sidebar.querySelector('nav'));
  document.querySelectorAll('.sidebar .nav').forEach(button=>{button.title=button.textContent.trim();});
  let stored=null;try{stored=localStorage.getItem('lich-truong-sidebar')}catch{}
  let collapsed=stored==='collapsed'||(stored!=='expanded'&&matchMedia('(min-width: 601px) and (max-width: 900px)').matches);
  function update(){app.classList.toggle('sidebar-collapsed',collapsed);app.classList.toggle('sidebar-expanded',!collapsed);toggle.setAttribute('aria-expanded',String(!collapsed));toggle.setAttribute('aria-label',collapsed?'Mở rộng thanh điều hướng':'Thu gọn thanh điều hướng');toggle.title=collapsed?'Mở rộng thanh điều hướng':'Thu gọn thanh điều hướng';toggle.textContent=collapsed?'›':'‹';}
  toggle.addEventListener('click',()=>{collapsed=!collapsed;try{localStorage.setItem('lich-truong-sidebar',collapsed?'collapsed':'expanded')}catch{}update()});update();
})();
