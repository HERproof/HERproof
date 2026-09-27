/* landing motion: word-by-word headline, scroll reveals, counting numbers, prevalence bars, tidying mess */
(function(){
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var h1 = document.querySelector("#landing h1");
  if(h1 && !reduce){
    h1.innerHTML = h1.textContent.split(" ").map(function(w, i){
      return '<span class="w" style="animation-delay:' + (0.3 + i * 0.1) + 's">' + w + '</span>';
    }).join(" ");
  }

  document.querySelectorAll("#landing .side.before .scrap").forEach(function(s, i){
    var r = (Math.random() * 10 - 5).toFixed(2);
    var x = (Math.random() * 90 - 45).toFixed(0);
    var y = (Math.random() * 70 - 35).toFixed(0);
    s.style.setProperty("--r", r + "deg");
    s.style.setProperty("--x", x + "px");
    s.style.setProperty("--y", y + "px");
    s.style.setProperty("--i", i);
  });

  function countTo(el){
    var target = el.getAttribute("data-n");
    var end = parseFloat(String(target).replace(/,/g, ""));
    if(isNaN(end)) return;
    if(reduce){ el.textContent = target; return; }
    var start = null, dur = 1200;
    requestAnimationFrame(function tick(ts){
      if(!start) start = ts;
      var p = Math.min(1, (ts - start) / dur);
      var v = Math.round(end * (1 - Math.pow(1 - p, 3)));
      el.textContent = v.toLocaleString();
      if(p < 1){ requestAnimationFrame(tick); } else { el.textContent = target; }
    });
  }

  function show(el){
    el.classList.add("shown");
    el.querySelectorAll("[data-n]").forEach(countTo);
    el.querySelectorAll(".cdcbar i").forEach(function(bar){
      bar.style.width = bar.getAttribute("data-w") + "%";
    });
  }

  var items = document.querySelectorAll("#landing .rise-in");
  if(!("IntersectionObserver" in window) || reduce){
    items.forEach(show);
    return;
  }
  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(e.isIntersecting){ show(e.target); io.unobserve(e.target); }
    });
  }, { rootMargin: "0px 0px -10% 0px", threshold: 0.12 });
  items.forEach(function(el){ io.observe(el); });
})();
