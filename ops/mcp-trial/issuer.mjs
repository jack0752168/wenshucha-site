import fs from 'node:fs';
import path from 'node:path';
import {atomicJsonUpdate} from './atomic-keys.mjs';
export function issueTrial(root,p){
 if(!/^[0-9a-f-]{36}$/.test(p.id)||!/^wsc_free_[0-9a-f]{32}$/.test(p.key)||!/^\d{4}-\d{2}-\d{2}$/.test(p.expires))throw Error('Invalid grant payload');
 const file=path.join(root,'keys.json'),marker='selfserve:'+p.id;
 const before=JSON.parse(fs.readFileSync(file,'utf8'));
 const existing=Object.entries(before).find(([k,e])=>e.selfserve_id===p.id);
 if(existing&&existing[0]!==p.key)throw Error('Grant identity conflict');
 atomicJsonUpdate(file,data=>{
  if(data[p.key]){const e=data[p.key];if(e.selfserve_id!==p.id||e.plan!=='free'||e.expires!==p.expires||e.revoked)throw Error('Existing key conflict');return null;}
  data[p.key]={plan:'free',limit:1000,body_limit:100,rpm:30,expires:p.expires,created:new Date().toISOString().slice(0,10),selfserve_id:p.id,note:`${p.profile.company}｜${p.profile.name}｜${p.profile.phone}｜${p.profile.email}｜自助免费一个月｜${marker}`};return data;
 });
 const after=JSON.parse(fs.readFileSync(file,'utf8'));if(after[p.key]?.selfserve_id!==p.id)throw Error('Grant readback failed');
 for(const [k,e]of Object.entries(before))if(JSON.stringify(after[k])!==JSON.stringify(e))throw Error('Existing customer changed');
 return {key:p.key,expires:after[p.key].expires};
}
