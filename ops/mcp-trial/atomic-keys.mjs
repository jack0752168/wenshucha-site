import fs from 'node:fs';
import crypto from 'node:crypto';
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function atomicJsonUpdate(file,update){
 const lock=file+'.write-lock',deadline=Date.now()+10000;let owned=false;
 while(!owned){try{fs.mkdirSync(lock,{mode:0o700});fs.writeFileSync(lock+'/pid',String(process.pid),{mode:0o600});owned=true;}catch(e){if(e.code!=='EEXIST')throw e;
  try{const pid=Number(fs.readFileSync(lock+'/pid','utf8'));if(pid>0){try{process.kill(pid,0);}catch(err){if(err.code==='ESRCH'){fs.rmSync(lock,{recursive:true});continue;}}}}catch{}
  if(Date.now()>deadline)throw Error('Key writer busy');Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,25);
 }}
 let temp;
 try{const original=JSON.parse(fs.readFileSync(file,'utf8')),updated=update(structuredClone(original));if(updated==null)return original;
  temp=file+'.'+process.pid+'.'+crypto.randomBytes(6).toString('hex')+'.tmp';const fd=fs.openSync(temp,'wx',0o600);try{fs.writeFileSync(fd,JSON.stringify(updated,null,2)+'\n');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}fs.renameSync(temp,file);return updated;
 }finally{if(temp&&fs.existsSync(temp))fs.unlinkSync(temp);fs.rmSync(lock,{recursive:true});}
}
export function mergeKeyChanges(file,baseline,desired){
 const changed=Object.keys({...baseline,...desired}).filter(k=>!equal(baseline[k],desired[k]));
 return atomicJsonUpdate(file,current=>{for(const k of changed){if(!equal(current[k],baseline[k])&&!equal(current[k],desired[k]))throw Error('Conflicting key update');if(desired[k]===undefined)delete current[k];else current[k]=desired[k];}return current;});
}
