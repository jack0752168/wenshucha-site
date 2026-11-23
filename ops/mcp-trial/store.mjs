import {DatabaseSync} from 'node:sqlite';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export class TrialError extends Error { constructor(status,code,message){super(message);Object.assign(this,{status,code});} }
const fail=(status,code,message)=>{throw new TrialError(status,code,message);};
export const day=(time)=>new Date(time+8*3600000).toISOString().slice(0,10);
export function monthLater(time){const [y,m,d]=day(time).split('-').map(Number);const target=new Date(Date.UTC(y,m,1));const last=new Date(Date.UTC(target.getUTCFullYear(),target.getUTCMonth()+1,0)).getUTCDate();return `${target.getUTCFullYear()}-${String(target.getUTCMonth()+1).padStart(2,'0')}-${String(Math.min(d,last)).padStart(2,'0')}`;}
export function emailIdentity(value){
 const email=String(value||'').trim().toLowerCase();
 if(email.length>160||! /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}$/.test(email)||email.includes('..'))fail(400,'email','请填写有效邮箱');
 let [local,domain]=email.split('@');local=local.split('+')[0];if(domain==='googlemail.com')domain='gmail.com';if(domain==='gmail.com')local=local.replaceAll('.','');return {email,identity:local+'@'+domain};
}
export function profileOf(b){
 const text=(v,min,max,label)=>{const s=String(v||'').normalize('NFKC').trim();if(s.length<min||s.length>max||/[\x00-\x1f\x7f<>]/.test(s))fail(400,'profile',`请填写有效${label}`);return s;};
 const name=text(b.name,2,60,'姓名'),company=text(b.company,2,120,'公司或机构名称');
 let phone=String(b.phone||'').replace(/[\s()-]/g,'');if(phone.startsWith('+86')&&phone.length===14)phone=phone.slice(3);
 if(!/^(?:1[3-9]\d{9}|\+[1-9]\d{6,14})$/.test(phone))fail(400,'phone','请填写有效手机号，境外号码请带国家区号');
 if(b.consent!==true)fail(400,'consent','请先同意领取及资料使用说明');
 return {name,company,phone};
}

export class TrialStore {
 constructor({file,secret,now=()=>Date.now(),requireWorker=true}){
  if(!secret||Buffer.from(secret,'hex').length!==32)throw Error('32-byte secret required');
  fs.mkdirSync(path.dirname(file),{recursive:true,mode:0o700});this.key=Buffer.from(secret,'hex');this.now=now;this.requireWorker=requireWorker;
  this.db=new DatabaseSync(file);fs.chmodSync(file,0o600);this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;
   CREATE TABLE IF NOT EXISTS challenges(session TEXT PRIMARY KEY,email_id TEXT,phone_id TEXT,profile TEXT,otp TEXT,expires INTEGER,created INTEGER,attempts INTEGER DEFAULT 0,delivered INTEGER DEFAULT 0,account_id TEXT);
   CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,email_id TEXT UNIQUE,phone_id TEXT UNIQUE,profile TEXT,key_cipher TEXT,expires TEXT,state TEXT,created INTEGER,crm_state TEXT DEFAULT 'pending');
   CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,kind TEXT,payload TEXT,state TEXT DEFAULT 'pending',lease TEXT,lease_until INTEGER DEFAULT 0,attempts INTEGER DEFAULT 0,available INTEGER,created INTEGER);
   CREATE TABLE IF NOT EXISTS rates(kind TEXT,identity TEXT,ts INTEGER);
   CREATE INDEX IF NOT EXISTS rate_lookup ON rates(kind,identity,ts);
   CREATE TABLE IF NOT EXISTS meta(name TEXT PRIMARY KEY,value TEXT);
  `);
 }
 hash(v){return crypto.createHmac('sha256',this.key).update(String(v)).digest('hex');}
 encrypt(v){const iv=crypto.randomBytes(12),c=crypto.createCipheriv('aes-256-gcm',this.key,iv);const bytes=Buffer.concat([c.update(JSON.stringify(v),'utf8'),c.final()]);return Buffer.concat([iv,c.getAuthTag(),bytes]).toString('base64');}
 decrypt(v){const b=Buffer.from(v,'base64'),d=crypto.createDecipheriv('aes-256-gcm',this.key,b.subarray(0,12));d.setAuthTag(b.subarray(12,28));return JSON.parse(Buffer.concat([d.update(b.subarray(28)),d.final()]).toString('utf8'));}
 transaction(fn){this.db.exec('BEGIN IMMEDIATE');try{const r=fn();this.db.exec('COMMIT');return r;}catch(e){this.db.exec('ROLLBACK');throw e;}}
 freshWorker(){const r=this.db.prepare('SELECT value FROM meta WHERE name=?').get('worker');return !!r&&this.now()-Number(r.value)<90000;}
 requireOnline(){if(this.requireWorker&&!this.freshWorker())fail(503,'worker_offline','领取服务暂不可用，请稍后重试');}
 rate(kind,identity,window,max){const n=this.db.prepare('SELECT COUNT(*) n FROM rates WHERE kind=? AND identity=? AND ts>?').get(kind,this.hash(identity),this.now()-window).n;if(n>=max)fail(429,'rate','操作较频繁，请稍后再试');}
 job(kind,payload){const id=crypto.randomUUID();this.db.prepare('INSERT INTO jobs(id,kind,payload,available,created) VALUES(?,?,?,?,?)').run(id,kind,this.encrypt(payload),this.now(),this.now());return id;}
 request(b,ip){
  this.requireOnline();if(b.website)fail(400,'request','申请信息不正确');
  const {email,identity}=emailIdentity(b.email),profile={...profileOf(b),email};
  return this.transaction(()=>{
   this.rate('mail',identity,60000,1);this.rate('mail',identity,86400000,5);this.rate('ip',ip,3600000,10);this.rate('ip',ip,86400000,30);this.rate('global','global',86400000,200);
   const emailId=this.hash(identity),phoneId=this.hash(profile.phone),now=this.now();
   const token=crypto.randomBytes(32).toString('hex'),session=this.hash(token),code=String(crypto.randomInt(100000,1000000));
   // One live OTP per email. A fresh request cannot preserve older OTP attempts.
   this.db.prepare('UPDATE challenges SET expires=0 WHERE email_id=? AND account_id IS NULL').run(emailId);
   this.db.prepare('INSERT INTO challenges(session,email_id,phone_id,profile,otp,expires,created) VALUES(?,?,?,?,?,?,?)').run(session,emailId,phoneId,this.encrypt(profile),this.hash(session+':'+code),now+600000,now);
   for(const [kind,id] of [['mail',identity],['ip',ip],['global','global']])this.db.prepare('INSERT INTO rates VALUES(?,?,?)').run(kind,this.hash(id),now);
   this.db.prepare('DELETE FROM rates WHERE ts<?').run(now-172800000);
   this.db.prepare('DELETE FROM challenges WHERE created<?').run(now-86400000);
   this.job('mail',{session,email,code});return {token,expires_in:600};
  });
 }
 challenge(token){const row=this.db.prepare('SELECT * FROM challenges WHERE session=?').get(this.hash(token||''));if(!row||this.now()-row.created>3600000)fail(401,'session','验证已过期，请重新获取验证码');return row;}
 verify(token,code){
  this.requireOnline();const c=this.challenge(token);
  if(c.account_id)return this.status(token);
  if(c.expires<this.now()||c.attempts>=6)fail(400,'otp_expired','验证码已失效，请重新获取');
  if(!c.delivered)fail(409,'mail_pending','验证码邮件正在发送，请稍候');
  this.db.prepare('UPDATE challenges SET attempts=attempts+1 WHERE session=?').run(c.session);
  const expected=Buffer.from(c.otp),actual=Buffer.from(this.hash(c.session+':'+String(code||'')));
  if(!crypto.timingSafeEqual(expected,actual))fail(400,'otp','验证码不正确');
  this.transaction(()=>{
   let account=this.db.prepare('SELECT * FROM accounts WHERE email_id=?').get(c.email_id);
   if(!account){
    if(this.db.prepare('SELECT id FROM accounts WHERE phone_id=?').get(c.phone_id))fail(409,'already_claimed','该手机号已领取，请使用原领取邮箱验证取回；需要协助可联系商务');
    const id=crypto.randomUUID(),key='wsc_free_'+crypto.randomBytes(16).toString('hex');
    this.db.prepare('INSERT INTO accounts(id,email_id,phone_id,profile,key_cipher,expires,state,created) VALUES(?,?,?,?,?,?,?,?)').run(id,c.email_id,c.phone_id,c.profile,this.encrypt(key),monthLater(this.now()),'pending',this.now());
    this.job('grant',{id,key,expires:monthLater(this.now()),profile:this.decrypt(c.profile),email_id:c.email_id,phone_id:c.phone_id});
    account={id};
   }
   this.db.prepare('UPDATE challenges SET account_id=?,otp=?,expires=0 WHERE session=?').run(account.id,'consumed',c.session);
  });return this.status(token);
 }
 status(token){const c=this.challenge(token);if(!c.account_id)return {state:'verification',mail_sent:!!c.delivered};const a=this.db.prepare('SELECT * FROM accounts WHERE id=?').get(c.account_id);
  if(day(this.now())>a.expires)return {state:'expired',expires:a.expires,message:'免费试用已结束，不可重复领取。需要继续使用可联系商务。'};
  if(a.state!=='active')return {state:'pending',message:'邮箱已验证，正在开通独立 Key，请稍候'};
  return {state:'active',key:this.decrypt(a.key_cipher),expires:a.expires,limit:1000,body_limit:100,plan:'free',crm:a.crm_state==='synced'?'synced':'pending'};
 }
 poll(worker){this.db.prepare('INSERT OR REPLACE INTO meta VALUES(?,?)').run('worker',String(this.now()));return this.transaction(()=>{
  const j=this.db.prepare("SELECT * FROM jobs WHERE state!='done' AND attempts<8 AND available<=? AND lease_until<? ORDER BY created LIMIT 1").get(this.now(),this.now());if(!j)return null;
  const lease=crypto.randomBytes(24).toString('hex');this.db.prepare("UPDATE jobs SET state='working',lease=?,lease_until=?,attempts=attempts+1 WHERE id=?").run(lease,this.now()+120000,j.id);
  return {id:j.id,kind:j.kind,lease,payload:this.decrypt(j.payload)};
 });}
 complete(b){return this.transaction(()=>{
  const j=this.db.prepare('SELECT * FROM jobs WHERE id=?').get(b.id);if(!j||j.lease!==b.lease)fail(409,'lease','Invalid job lease');if(j.state==='done')return {ok:true};
  const p=this.decrypt(j.payload);
  if(b.ok!==true){this.db.prepare("UPDATE jobs SET state='pending',lease_until=0,available=? WHERE id=?").run(this.now()+Math.min(300000,15000*2**Math.min(j.attempts,4)),j.id);return {ok:true};}
  if(j.kind==='mail')this.db.prepare('UPDATE challenges SET delivered=1 WHERE session=? AND expires>?').run(p.session,this.now());
  else if(j.kind==='grant'){if(b.key!==p.key||b.expires!==p.expires)fail(409,'grant','Grant verification mismatch');this.db.prepare("UPDATE accounts SET state='active' WHERE id=?").run(p.id);}
  this.db.prepare("UPDATE jobs SET state='done',lease_until=0,payload=? WHERE id=?").run(this.encrypt({id:p.id||null}),j.id);return {ok:true};
 });}
 crmNext(){const a=this.db.prepare("SELECT * FROM accounts WHERE state='active' AND crm_state!='synced' ORDER BY created LIMIT 1").get();if(!a)return null;const key=this.decrypt(a.key_cipher);return {id:a.id,profile:this.decrypt(a.profile),email_id:a.email_id,expires:a.expires,issued_day:day(a.created),key_mask:key.slice(0,9)+'…'+key.slice(-4),plan:'free',source:'mcp-selfserve',email_verified:true,phone_verified:false};}
 crmAck(id){this.db.prepare("UPDATE accounts SET crm_state='synced' WHERE id=? AND state='active'").run(id);return {ok:true};}
 close(){this.db.close();}
}
