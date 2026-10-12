(function () {
  "use strict";
  if (window.WSCFunnel) return;
  var version = "ctr-funnel-20261012", cookie = "wsc_funnel_v1", memory = null, lastPage = "";
  var events = ["page_view", "cta_search", "cta_report", "cta_mcp", "contact_email", "contact_phone", "search_start", "search_success", "search_empty", "search_error", "fulltext_open", "fulltext_partial", "lead_start"];
  var sources = ["bing", "google", "baidu", "zhihu", "baijiahao", "weixin", "chatgpt", "copilot", "sogou", "360", "quark", "duckduckgo", "direct", "other"];
  function uuid() { return crypto.randomUUID(); }
  function context() {
    var qaParam = new URLSearchParams(location.search).get("wsc_qa");
    if (memory && (qaParam === "1" || qaParam === "0") && memory.qa !== (qaParam === "1")) memory = null;
    if (memory && memory.until > Date.now()) return memory;
    try {
      var raw = document.cookie.split("; ").find(function (x) { return x.indexOf(cookie + "=") === 0; });
      if (raw) {
        var stored = JSON.parse(decodeURIComponent(raw.slice(cookie.length + 1)));
        if (/^[a-f0-9-]{36}$/.test(stored.sid) && stored.until > Date.now() && sources.indexOf(stored.source) >= 0 && ((qaParam !== "1" && qaParam !== "0") || stored.qa === (qaParam === "1"))) memory = stored;
      }
    } catch (_) {}
    if (!memory || memory.until <= Date.now()) {
      var query = new URLSearchParams(location.search), source = "direct", medium = "direct", campaign = "";
      var utm = (query.get("utm_source") || "").toLowerCase();
      if (utm) { source = sources.indexOf(utm) >= 0 ? utm : "other"; medium = "campaign"; }
      else {
        try {
          var host = new URL(document.referrer).hostname.toLowerCase();
          if (host !== "wenshucha.com" && !host.endsWith(".wenshucha.com")) {
            source = "other"; medium = "referral";
            [["bing.com", "bing"], ["google.com", "google"], ["google.com.hk", "google"], ["baidu.com", "baidu"], ["zhihu.com", "zhihu"], ["weixin.qq.com", "weixin"], ["chatgpt.com", "chatgpt"], ["copilot.microsoft.com", "copilot"], ["sogou.com", "sogou"], ["so.com", "360"], ["sm.cn", "quark"], ["duckduckgo.com", "duckduckgo"]].some(function (pair) {
              if (host === pair[0] || host.endsWith("." + pair[0])) { source = pair[1]; medium = ["bing", "google", "baidu", "sogou", "360", "quark", "duckduckgo"].indexOf(source) >= 0 ? "organic" : "referral"; return true; } return false;
            });
          }
        } catch (_) {}
      }
      var c = query.get("utm_campaign") || "";
      if (/^[a-zA-Z0-9_-]{1,80}$/.test(c)) campaign = c;
      memory = { sid: uuid(), source: source, medium: medium, campaign: campaign, qa: query.get("wsc_qa") === "1", until: Date.now() + 1800000 };
    }
    memory.until = Date.now() + 1800000;
    try { document.cookie = cookie + "=" + encodeURIComponent(JSON.stringify(memory)) + "; Path=/; Max-Age=1800; SameSite=Lax" + (location.protocol === "https:" ? "; Secure" : "") + (location.hostname === "wenshucha.com" || location.hostname.endsWith(".wenshucha.com") ? "; Domain=wenshucha.com" : ""); } catch (_) {}
    return memory;
  }
  function path() {
    var p = location.pathname;
    if (/^\/cases\//.test(p)) return "/cases/detail";
    return /^\/[a-zA-Z0-9_./-]{0,179}$/.test(p) ? p : "/other";
  }
  function event(name, fields) {
    try {
      if (events.indexOf(name) < 0) return;
      var ctx = context(); if (!ctx) return;
      var record = { sid: ctx.sid, source: ctx.source, medium: ctx.medium, campaign: ctx.campaign, qa: ctx.qa, eid: uuid(), event: name, site: location.hostname === "tob.wenshucha.com" ? "tob" : "www", path: path(), surface: (fields || {}).surface || "page", version: version, screen: Math.min(20000, screen.width || 0) };
      if (typeof (fields || {}).status === "number") record.status = fields.status;
      // Never send the URL query, search terms, case identifiers, body text or contact details.
      var endpoint = /^(localhost|127\.0\.0\.1)$/.test(location.hostname) ? location.origin + "/api/funnel" : "https://tob.wenshucha.com/api/funnel";
      fetch(endpoint, { method: "POST", mode: "cors", credentials: "omit", keepalive: true, headers: { "Content-Type": "application/json" }, body: JSON.stringify(record) }).catch(function () {});
    } catch (_) {}
  }
  function page() { var current = location.pathname; if (current !== lastPage) { lastPage = current; event("page_view"); } }
  function preserve(params) {
    var incoming = new URLSearchParams(location.search);
    ["utm_source", "utm_medium", "utm_campaign", "wsc_qa"].forEach(function (key) {
      var value = incoming.get(key); if (value && /^[a-zA-Z0-9_-]{1,80}$/.test(value)) params.set(key, value);
    });
  }
  window.WSCFunnel = { context: context, event: event, page: page, preserve: preserve };
  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest ? e.target.closest("a") : null; if (!a) return;
    var href = a.getAttribute("href") || "";
    if (/^mailto:/i.test(href)) event("contact_email");
    else if (/^tel:/i.test(href)) event("contact_phone");
    else {
      try {
        var u = new URL(href, location.href);
        if (u.hostname !== "wenshucha.com" && !u.hostname.endsWith(".wenshucha.com")) return;
        if (u.pathname === "/cases" || u.pathname === "/case-search/") event("cta_search");
        else if (u.pathname === "/data-report/") event("cta_report");
        else if (u.pathname === "/mcp/" || u.pathname === "/mcp/apply/") event("cta_mcp");
      } catch (_) {}
    }
  }, true);
  page();
})();
