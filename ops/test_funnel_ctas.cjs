const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const source = fs.readFileSync(require('node:path').join(__dirname, '../assets/funnel-v1.js'), 'utf8');
const origins = ['/', '/pricing/', '/case-search/', '/blog/similar-case-search-completeness-guide.html', '/blog/limitation-period-defense-tolling-search.html'];
const cases = origins.map(path => ({path, dest: '/case-research/', name: 'cta_search', surface: 'inline'}));
cases.push({path: '/case-research/', dest: 'https://tob.wenshucha.com/research/', name: 'cta_search', surface: 'report'},
  {path: '/', dest: '/case-search/', name: 'cta_search', surface: 'detail'},
  {path: '/', dest: '/mcp/quickstart/', name: 'cta_mcp', surface: 'mcp'});
for (const item of cases) {
  const events = [];
  let click;
  const location = new URL('https://www.wenshucha.com'+item.path+'?wsc_qa=1');
  const document = {cookie:'', referrer:'', addEventListener(name, fn) {if(name === 'click') click=fn;}};
  const context = {window:{}, document, location, URL, URLSearchParams, Date, crypto, screen:{width:1280},
    fetch(url, opts) {events.push(JSON.parse(opts.body));return Promise.resolve({ok:true});}};
  vm.runInNewContext(source, context);
  click({target:{closest(){return {getAttribute(){return item.dest;}};}}});
  const event = events[events.length-1];
  assert.equal(event.event, item.name);
  assert.equal(event.surface, item.surface);
  assert.equal(event.path, item.path);
  assert.equal(event.version, 'ctr-funnel-20261012');
  assert(events.every(e=>e.qa === true));
  assert(!Object.keys(event).some(k=>['destination','email','question'].includes(k)));
}
console.log(JSON.stringify({status:'pass', cases:cases.length, all_qa:true, backend_contract_unchanged:true}));
