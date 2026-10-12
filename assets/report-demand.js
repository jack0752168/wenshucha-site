(function () {
  "use strict";
  var form = document.getElementById("reportDemand"); if (!form) return;
  var button = form.querySelector("button[type=submit]"), message = document.getElementById("reportDemandStatus"), requestId = "", started = false;
  form.addEventListener("focusin", function () {
    if (!started) { started = true; if (window.WSCFunnel) window.WSCFunnel.event("lead_start", { surface: "report" }); }
  });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!form.reportValidity()) return;
    try {
      if (!requestId) requestId = crypto.randomUUID();
      var data = { request_id: requestId, consent: form.elements.consent.checked };
      ["topic", "institution", "role", "email", "purpose", "timeframe", "website"].forEach(function (key) { data[key] = form.elements[key].value.trim(); });
      if (window.WSCFunnel) {
        var c = window.WSCFunnel.context();
        if (c) data.funnel = { sid: c.sid, source: c.source, medium: c.medium, campaign: c.campaign, qa: c.qa };
      }
      button.disabled = true; button.textContent = "提交中…"; message.textContent = "";
      fetch("https://tob.wenshucha.com/api/report-demand", { method: "POST", mode: "cors", credentials: "omit", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) })
        .then(function (r) { return r.json().then(function (j) { return { accepted: r.ok && j.ok, data: j }; }); })
        .then(function (result) {
          if (!result.accepted) throw new Error(result.data.error || "暂时无法提交，请稍后重试或通过下方邮箱联系。");
          form.hidden = true;
          message.textContent = "需求已保存。我们会通过你填写的邮箱联系你，确认检索范围和交付口径。需求编号：" + result.data.id;
          message.className = "demand-status demand-success";
        })
        .catch(function (error) { message.textContent = error.message || "网络异常，可通过下方邮箱联系。"; button.disabled = false; button.textContent = "提交研究需求"; });
    } catch (_) { message.textContent = "当前浏览器暂不能提交表单，请通过下方邮箱联系。"; }
  });
})();
