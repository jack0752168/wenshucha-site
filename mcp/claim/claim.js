'use strict';
const $=id=>document.getElementById(id),api='/api/mcp-trial/';let activeKey='',pollTimer;
function message(text){$('message').textContent=text;}
function show(id){for(const name of ['start','verification','waiting','result'])$(name).hidden=name!==id;}
async function request(path,body){const response=await fetch(api+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',cache:'no-store',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});let data;try{data=await response.json();}catch{throw Error('服务暂不可用，请稍后再试');}if(!response.ok)throw Error(data.error||'暂时无法完成，请稍后重试');return data;}
function config(){const key=activeKey;let server;switch($('client').value){case'desktop':server={command:'npx',args:['-y','mcp-remote','https://mcp.wenshucha.com/mcp','--header','x-api-key:'+key]};break;case'claude-code':server={type:'http',url:'https://mcp.wenshucha.com/mcp',headers:{'x-api-key':key}};break;default:server={url:'https://mcp.wenshucha.com/mcp',headers:{'x-api-key':key}};}$('config').value=JSON.stringify({mcpServers:{wenshucha:server}},null,2);}
function display(data){if(data.state==='active'){clearTimeout(pollTimer);activeKey=data.key;$('key').value=data.key;$('expiry').textContent=data.expires;config();show('result');message('每次工具返回中的 _quota 可查看余量。');$('crm-status').textContent='资料仅用于服务开通、接入支持及试用回访。';return;}
 if(data.state==='expired'){clearTimeout(pollTimer);show('start');message(data.message+'原到期日：'+data.expires);return;}
 if(data.state==='pending'){show('waiting');pollTimer=setTimeout(poll,3500);}}
async function poll(){try{display(await request('status'));}catch(e){message(e.message+'；无需重复领取，可稍后刷新页面。');pollTimer=setTimeout(poll,12000);}}
$('profile-form').addEventListener('submit',async event=>{event.preventDefault();$('send').disabled=true;message('正在发送验证码…');try{const form=new FormData(event.currentTarget);const body=Object.fromEntries(form);body.consent=$('consent').checked;await request('request',body);$('email-display').textContent=body.email;show('verification');$('code').focus();message('请查看验证码邮件。');}catch(e){message(e.message);}finally{$('send').disabled=false;}});
$('code-form').addEventListener('submit',async event=>{event.preventDefault();$('verify').disabled=true;message('正在验证…');try{display(await request('verify',{code:$('code').value.trim()}));}catch(e){message(e.message);}finally{$('verify').disabled=false;}});
$('back').addEventListener('click',()=>{clearTimeout(pollTimer);show('start');message('如需重新发送，请与上次发送间隔至少一分钟。');});
$('client').addEventListener('change',config);
async function copy(id){try{await navigator.clipboard.writeText($(id).value);message('已复制，请妥善保存。');}catch{$(id).focus();$(id).select();message('请长按或使用复制快捷键复制所选内容。');}}
$('copy-key').addEventListener('click',()=>copy('key'));$('copy-config').addEventListener('click',()=>copy('config'));
request('status').then(display).catch(()=>{});
