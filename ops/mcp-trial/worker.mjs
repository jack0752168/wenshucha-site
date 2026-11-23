import fs from 'node:fs';
import {sendCode} from './smtp.mjs';
import {issueTrial} from './issuer.mjs';
const config=JSON.parse(fs.readFileSync(process.env.WSC_TRIAL_CONFIG||'/Users/jack/.config/wsc-mcp-trial/worker.json','utf8'));
if(!config.url.startsWith('https://')||!config.token)throw Error('Invalid worker configuration');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function api(path,body){const r=await fetch(config.url+'/internal/'+path,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+config.token},body:JSON.stringify(body),signal:AbortSignal.timeout(25000)});if(!r.ok)throw Error('API '+r.status);return r.json();}
for(;;){try{const {job}=await api('poll',{worker:'mini-trial-worker'});if(!job){await pause(4000);continue;}
 let result;try{if(job.kind==='mail'){await sendCode(config.smtp,job.payload.email,job.payload.code);result={ok:true};}else if(job.kind==='grant'){result={ok:true,...issueTrial(config.mcpRoot||'/Users/jack/wsc-mcp',job.payload)};}else throw Error('Unknown job');}
 catch{result={ok:false};console.error(JSON.stringify({event:'job_retry',kind:job.kind,at:new Date().toISOString()}));}
 await api('complete',{id:job.id,lease:job.lease,...result});
 }catch{console.error(JSON.stringify({event:'worker_unavailable',at:new Date().toISOString()}));await pause(15000);}}
