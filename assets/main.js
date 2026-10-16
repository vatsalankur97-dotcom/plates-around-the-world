(()=>{const RM=matchMedia('(prefers-reduced-motion: reduce)').matches,$=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
$('.menu')?.addEventListener('click',()=>$('nav ul').classList.toggle('open'));
$$('form[data-placeholder]').forEach(f=>f.addEventListener('submit',e=>{e.preventDefault();f.innerHTML='<p style="margin:12px auto">Thanks! (Placeholder form, not yet connected.)</p>'}));
const h=$('header');const onS=()=>h&&h.classList.toggle('small',scrollY>40);addEventListener('scroll',onS,{passive:true});onS();
// word reveal
$$('[data-words]').forEach(el=>{let i=0;el.innerHTML=el.innerHTML.split(/(<[^>]+>|\s+)/).map(t=>/^\s+$|^</.test(t)||!t?t:`<span class="w" style="animation-delay:${.15+(i++)*.12}s">${t}</span>`).join('')});
// rotating city
const rb=$('.rot b');if(rb){const L=JSON.parse(rb.dataset.list);let k=0;setInterval(()=>{rb.classList.add('out');setTimeout(()=>{k=(k+1)%L.length;rb.textContent=L[k];rb.classList.remove('out')},350)},2200)}
// reveal
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.12});
$$('.rv').forEach(el=>io.observe(el));
if(RM)return;
// cursor
if(matchMedia('(hover:hover)').matches){const c=document.createElement('div');c.className='cursor';document.body.appendChild(c);let x=0,y=0,cx=0,cy=0;
addEventListener('mousemove',e=>{x=e.clientX;y=e.clientY;c.style.opacity=1});(function t(){cx+=(x-cx)*.2;cy+=(y-cy)*.2;c.style.transform=`translate(${cx}px,${cy}px) translate(-50%,-50%)`;requestAnimationFrame(t)})();
$$('a.card,.insta a,.pin,.btn').forEach(el=>{el.addEventListener('mouseenter',()=>c.classList.add('big'));el.addEventListener('mouseleave',()=>c.classList.remove('big'))});
// magnetic
$$('.btn').forEach(b=>{b.addEventListener('mousemove',e=>{const r=b.getBoundingClientRect();b.style.transform=`translate(${(e.clientX-r.left-r.width/2)*.25}px,${(e.clientY-r.top-r.height/2)*.35}px)`});b.addEventListener('mouseleave',()=>b.style.transform='')});
// tilt
$$('a.card').forEach(cd=>{const im=cd.querySelector('img');cd.addEventListener('mousemove',e=>{const r=cd.getBoundingClientRect(),px=(e.clientX-r.left)/r.width-.5,py=(e.clientY-r.top)/r.height-.5;cd.style.transform=`perspective(900px) rotateY(${px*10}deg) rotateX(${-py*10}deg)`;im.style.transform=`scale(1.08) translate(${-px*14}px,${-py*14}px)`});cd.addEventListener('mouseleave',()=>{cd.style.transform='';im.style.transform=''})})}
// hero parallax
const st=$('.logo-stage');if(st)addEventListener('scroll',()=>{st.style.transform=`translateY(${scrollY*.15}px) rotate(${scrollY*.02}deg)`},{passive:true});
})();
// spin the plate (works even with reduced motion)
(()=>{const b=document.querySelector('#spin');if(!b)return;const P=document.querySelector('.spinplate'),out=document.querySelector('.spin-result'),lbl=P.querySelector('b');
const O=[["Pad Thai in Bangkok","articles/best-street-food-bangkok.html"],["Crab omelette at Jay Fai","articles/best-street-food-bangkok.html"],["Pastel de nata in Lisbon","articles/where-to-eat-lisbon.html"],["Garlic prawns at Ramiro","articles/where-to-eat-lisbon.html"],["Butter chicken, Delhi-style","articles/butter-chicken.html"]];
let rot=0;b.addEventListener('click',()=>{const o=O[Math.floor(Math.random()*O.length)];rot+=1080+Math.random()*360;P.style.transform=`rotate(${rot}deg)`;lbl.textContent='…';out.textContent='';
setTimeout(()=>{P.style.transform=`rotate(${Math.round(rot/360)*360}deg)`;lbl.textContent=o[0];out.innerHTML=`<a href="${o[1]}">${o[0]} →</a>`},1600)})})();
