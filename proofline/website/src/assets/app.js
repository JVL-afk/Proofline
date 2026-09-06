/* Proofline — minimal progressive enhancement. No dependencies, no tracking. */
(function () {
  "use strict";

  document.documentElement.classList.remove("no-js");

  // Current year in the footer.
  var y = document.getElementById("year");
  if (y) { y.textContent = String(new Date().getFullYear()); }

  // Reveal-on-scroll. Falls back to fully visible if unsupported or reduced-motion.
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var items = document.querySelectorAll(".reveal");

  if (reduce || !("IntersectionObserver" in window)) {
    items.forEach(function (el) { el.classList.add("is-visible"); });
    return;
  }

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        io.unobserve(entry.target);
      }
    });
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });

  items.forEach(function (el) { io.observe(el); });
})();
