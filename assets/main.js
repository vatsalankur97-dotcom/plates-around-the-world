(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const menu = $(".menu");
  const list = $("#site-nav ul");
  const searchBtn = $(".search-toggle");
  const searchSlot = $(".search-slot");
  menu?.addEventListener("click", () => {
    const open = list.classList.toggle("open");
    menu.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      searchSlot?.classList.remove("open");
      searchBtn?.setAttribute("aria-expanded", "false");
    }
  });
  searchBtn?.addEventListener("click", () => {
    const open = searchSlot.classList.toggle("open");
    searchBtn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      list?.classList.remove("open");
      menu?.setAttribute("aria-expanded", "false");
      searchSlot.querySelector("input")?.focus();
    }
  });
  const privacy = $("#privacy");
  if (privacy && location.hash === "#privacy") privacy.open = true;
  $$('a[href="#privacy"]').forEach((link) => {
    link.addEventListener("click", () => {
      if (privacy) privacy.open = true;
    });
  });
  // Legacy mailto path. Backend's Netlify form must not use data-subscribe.
  $$("form[data-subscribe]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = form.querySelector("input").value;
      location.href = "mailto:plates.arounddtheworld@gmail.com?subject=" + encodeURIComponent("Subscribe") + "&body=" + encodeURIComponent("Please add " + value + " to the Plates Around the World newsletter.");
      form.insertAdjacentHTML("beforeend", "<p>Thanks. Your email app should open so you can confirm.</p>");
    });
  });
  // Approved copy: the newsletter action stays a placeholder until a tool is chosen.
  $$('form[name="newsletter"]').forEach((form) => {
    form.addEventListener("submit", (event) => {
      if ((form.getAttribute("action") || "").indexOf("NEWSLETTER_FORM_ACTION") === -1) return;
      event.preventDefault();
      if (form.querySelector(".form-pending")) return;
      form.insertAdjacentHTML("beforeend", '<p class="form-pending">The newsletter tool is not connected yet. This form action is still a placeholder.</p>');
    });
  });
  const city = $(".rot b");
  if (city && !reduce) {
    const names = JSON.parse(city.dataset.list);
    let index = 0;
    setInterval(() => {
      index = (index + 1) % names.length;
      city.textContent = names[index];
    }, 2200);
  }
  if (!reduce && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          observer.unobserve(entry.target);
        }
      });
    }, {threshold: 0.12});
    $$(".rv").forEach((el) => observer.observe(el));
  } else {
    $$(".rv").forEach((el) => el.classList.add("in"));
  }
  document.querySelector("[data-print]")?.addEventListener("click", () => print());
  const plate = $(".spinplate");
  const spin = $("#spin");
  if (!plate || !spin) return;
  const result = $(".spin-result");
  const label = plate.querySelector("b");
  const options = [
    ["Pad Thai in Bangkok", "/articles/best-street-food-bangkok"],
    ["Crab omelette at Jay Fai", "/articles/best-street-food-bangkok"],
    ["Pastel de nata in Lisbon", "/articles/where-to-eat-lisbon"],
    ["Garlic prawns at Ramiro", "/articles/where-to-eat-lisbon"],
    ["Butter chicken, Delhi-style", "/articles/butter-chicken"],
    ["Yakitori in Shinjuku", "/articles/where-to-eat-tokyo"],
    ["Tonkotsu ramen", "/articles/ramen-101"]
  ];
  let angle = 0;
  spin.addEventListener("click", () => {
    const choice = options[Math.floor(Math.random() * options.length)];
    angle += 1080;
    plate.style.transform = "rotate(" + angle + "deg)";
    label.textContent = "…";
    result.textContent = "";
    setTimeout(() => {
      label.textContent = choice[0];
      result.innerHTML = '<a href="' + choice[1] + '">' + choice[0] + "</a>";
    }, reduce ? 0 : 1400);
  });
})();
