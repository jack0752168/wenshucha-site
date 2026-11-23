import http from 'node:http';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {TrialStore,TrialError} from './store.mjs';
const prefix='/api/mcp-trial';
const secureEqual=(a,b)=>!!a&&!!b&&Buffer.byteLength(a)===Buffer.byteLength(b)&&crypto.timingSafeEqual(Buffer.from(a),Buffer.from(b));
export function createServer({store,workerToken,crmToken,origin='https://www.wenshucha.com',secureCookie=true}){
 return http.createServer(async(req,res)=>{
  res.setHeader('Cache-Control','no-store');res.setHeader('Content-Type','application/json; charset=utf-8');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');
  const send=(status,value)=>{res.writeHead(status);res.end(JSON.stringify(value));};
  const cookie=()=>{const value=(req.headers.cookie||'').split(';').map(x=>x.trim()).find(x=>x.startsWith('__Secure-wsc_trial='));return value?.slice('__Secure-wsc_trial='.length)||'';};
  try{
   const path=req.url.split('?')[0];
   if(req.method==='GET'&&path===prefix+'/health')return send(200,{ok:true,ready:store.freshWorker()});
   if(req.method==='GET'&&path===prefix+'/status')return send(200,store.status(cookie()));
   if(req.method!=='POST')throw new TrialError(405,'method','请求方式不支持');
   const internal=path.startsWith(prefix+'/internal/');
   const crm=path.startsWith(prefix+'/internal/crm/');
   if(internal){if(!secureEqual(req.headers.authorization||'','Bearer '+(crm?crmToken:workerToken)))throw new TrialError(401,'auth','Unauthorized');}
   else if(req.headers.origin!==origin)throw new TrialError(403,'origin','请从文书查领取页面提交');
   if(!String(req.headers['content-type']||'').toLowerCase().startsWith('application/json'))throw new TrialError(415,'content_type','请使用JSON提交');
   let raw='';for await(const chunk of req){raw+=chunk;if(Buffer.byteLength(raw)>12000)throw new TrialError(413,'size','提交内容过长');}
   let b;try{b=JSON.parse(raw);}catch{throw new TrialError(400,'json','提交格式不正确');}if(!b||typeof b!=='object'||Array.isArray(b))throw new TrialError(400,'json','提交格式不正确');
   if(path===prefix+'/request'){
    const result=store.request(b,req.headers['x-real-ip']||req.socket.remoteAddress);res.setHeader('Set-Cookie',`__Secure-wsc_trial=${result.token}; Path=${prefix}/; HttpOnly; SameSite=Strict; Max-Age=3600${secureCookie?'; Secure':''}`);return send(200,{ok:true,expires_in:result.expires_in,message:'验证码正在发送，请查看邮箱（含垃圾邮件）'});
   }
   if(path===prefix+'/verify')return send(200,store.verify(cookie(),b.code));
   if(path===prefix+'/internal/poll')return send(200,{job:store.poll(b.worker)});
   if(path===prefix+'/internal/complete')return send(200,store.complete(b));
   if(path===prefix+'/internal/crm/poll')return send(200,{lead:store.crmNext()});
   if(path===prefix+'/internal/crm/ack')return send(200,store.crmAck(b.id));
   throw new TrialError(404,'not_found','Not found');
  }catch(e){if(!res.headersSent)send(e instanceof TrialError?e.status:500,{ok:false,code:e instanceof TrialError?e.code:'internal',error:e instanceof TrialError?e.message:'服务暂不可用，请稍后重试'});else res.end();}
 });
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 for(const k of ['WSC_TRIAL_SECRET','WSC_TRIAL_WORKER_TOKEN','WSC_TRIAL_CRM_TOKEN'])if((process.env[k]||'').length<48)throw Error('Missing '+k);
 const store=new TrialStore({file:process.env.WSC_TRIAL_DB||'/var/lib/wsc-mcp-trial/trial.sqlite',secret:process.env.WSC_TRIAL_SECRET});
 const server=createServer({store,workerToken:process.env.WSC_TRIAL_WORKER_TOKEN,crmToken:process.env.WSC_TRIAL_CRM_TOKEN});
 server.requestTimeout=15000;server.headersTimeout=10000;server.listen(Number(process.env.PORT||8791),'127.0.0.1');
}
