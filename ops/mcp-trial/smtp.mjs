import tls from 'node:tls';
import crypto from 'node:crypto';
export async function sendCode({host='smtp.exmail.qq.com',port=465,user,password},email,code){
 if(!/^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}$/i.test(email)||!/^\d{6}$/.test(code))throw Error('Invalid mail payload');
 const socket=tls.connect({host,port,servername:host,rejectUnauthorized:true});let buffer='',responses=[],waiter;
 socket.setTimeout(20000,()=>socket.destroy(Error('SMTP timeout')));
 function deliver(err,value){if(waiter){const w=waiter;waiter=null;err?w.reject(err):w.resolve(value);}else if(!err)responses.push(value);}
 socket.on('data',chunk=>{buffer+=chunk.toString('utf8');while(buffer.includes('\r\n')){const n=buffer.indexOf('\r\n'),line=buffer.slice(0,n);buffer=buffer.slice(n+2);if(/^\d{3} /.test(line))deliver(null,Number(line.slice(0,3)));}});
 let fatal;socket.on('error',err=>{fatal=err;deliver(err);});socket.on('close',()=>{fatal=fatal||Error('SMTP closed');if(waiter)deliver(fatal);});
 const read=()=>fatal?Promise.reject(fatal):responses.length?Promise.resolve(responses.shift()):new Promise((resolve,reject)=>{waiter={resolve,reject};});
 async function expect(allowed){const code=await read();if(!allowed.includes(code))throw Error('SMTP rejected ('+code+')');}
 async function cmd(text,allowed){socket.write(text+'\r\n');await expect(allowed);}
 try{
  await expect([220]);await cmd('EHLO wenshucha.com',[250]);await cmd('AUTH LOGIN',[334]);await cmd(Buffer.from(user).toString('base64'),[334]);await cmd(Buffer.from(password).toString('base64'),[235]);
  await cmd('MAIL FROM:<'+user+'>',[250]);await cmd('RCPT TO:<'+email+'>',[250,251]);await cmd('DATA',[354]);
  const body=`您的文书查 MCP 领取验证码：${code}\n\n验证码10分钟内有效，请勿转发。验证后可领取一个月免费试用。\n如非本人申请，请忽略此邮件。\n\n文书查 · 深圳星谱网络科技有限公司\nhttps://www.wenshucha.com/mcp/claim/`;
  const mime=['From: =?UTF-8?B?'+Buffer.from('文书查').toString('base64')+'?= <'+user+'>','To: <'+email+'>','Subject: =?UTF-8?B?'+Buffer.from('文书查 MCP 领取验证码').toString('base64')+'?=','Date: '+new Date().toUTCString(),'Message-ID: <'+crypto.randomUUID()+'@wenshucha.com>','MIME-Version: 1.0','Content-Type: text/plain; charset=UTF-8','Content-Transfer-Encoding: base64','',Buffer.from(body).toString('base64').match(/.{1,76}/g).join('\r\n'),''].join('\r\n');
  socket.write(mime+'\r\n.\r\n');await expect([250]);socket.end('QUIT\r\n');
 }finally{socket.destroy();}
}
