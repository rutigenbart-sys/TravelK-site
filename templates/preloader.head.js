(function(){var d=document.documentElement,K="tkp2",seen=0;
try{seen=sessionStorage.getItem(K)?1:0}catch(e){try{seen=/(?:^|; )tkp2=1/.test(document.cookie)?1:0}catch(_){}}
if(!seen){try{if(document.referrer&&new URL(document.referrer).host===location.host)seen=1}catch(e){}}
if(seen)return;
try{sessionStorage.setItem(K,"1")}catch(e){try{document.cookie="tkp2=1; path=/; SameSite=Lax"}catch(_){}}
window.__tk0=Date.now();
window.__tkrm=!!(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches);
d.classList.add("pl")})();