(function () {
  var input = document.querySelector("[data-site-search]");
  var out = document.querySelector("[data-site-search-results]");
  if (!input || !out) return;
  var items = [];
  fetch("/data/search-index.json")
    .then(function (response) { return response.json(); })
    .then(function (data) { items = data; })
    .catch(function () { items = []; });
  function text(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  input.addEventListener("input", function () {
    var query = input.value.trim().toLowerCase();
    if (!query) {
      out.hidden = true;
      out.innerHTML = "";
      return;
    }
    var hits = items.filter(function (item) {
      var haystack = (item.title + " " + item.description + " " + item.text).toLowerCase();
      return haystack.indexOf(query) !== -1;
    }).slice(0, 8);
    out.hidden = false;
    if (!hits.length) {
      out.innerHTML = "<li>No matches</li>";
      return;
    }
    out.innerHTML = hits.map(function (item) {
      return '<li><a href="' + text(item.url) + '">' + text(item.title) + "</a></li>";
    }).join("");
  });
})();
