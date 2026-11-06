(() => {
  'use strict';
  function revealScope(){
    let id;try{id=decodeURIComponent(location.hash.slice(1));}catch{return;}
    const target=document.getElementById(id);if(!target)return;
    const details=target.closest('details.compact-details')||target.querySelector('details.compact-details');
    if(details)details.open=true;
  }
  revealScope();window.addEventListener('hashchange',revealScope);
})();
