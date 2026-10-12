(function () {
  "use strict";
  var form = document.getElementById("caseEntry"); if (!form) return;
  form.addEventListener("submit", function () {
    if (!form.checkValidity()) return;
    if (window.WSCFunnel) window.WSCFunnel.event("cta_search");
    var params = new URLSearchParams(location.search);
    ["utm_source", "utm_medium", "utm_campaign", "wsc_qa"].forEach(function (key) {
      var value = params.get(key);
      if (value && /^[a-zA-Z0-9_-]{1,80}$/.test(value)) {
        var input = document.createElement("input"); input.type = "hidden"; input.name = key; input.value = value; form.appendChild(input);
      }
    });
  });
})();
