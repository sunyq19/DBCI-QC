import http from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import path from 'node:path';
import * as flow from '../app/api/flow/route.ts';
import * as access from '../app/api/access/route.ts';
import * as attachments from '../app/api/attachments/route.ts';
import {env} from './env.mjs';
const host=process.env.FLOW_BIND||'127.0.0.1',port=Number(process.env.FLOW_PORT||18770);
const publicOrigin=process.env.FLOW_PUBLIC_ORIGIN;
if(publicOrigin){
 const parsed=new URL(publicOrigin);
 if(!['http:','https:'].includes(parsed.protocol)||parsed.origin!==publicOrigin)throw new Error('FLOW_PUBLIC_ORIGIN must be an exact http(s) origin without a path');
}
const staticRoot=path.resolve('public'),routes={'/api/flow':flow,'/api/access':access,'/api/attachments':attachments};
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp','.pdf':'application/pdf'};
const server=http.createServer(async(req,res)=>{
 try{
  // The proxy preserves Host. Use configured HTTPS origin, never caller-supplied forwarding headers.
  if(publicOrigin&&(req.headers.host!==new URL(publicOrigin).host||(req.headers.origin&&req.headers.origin!==publicOrigin))){
   res.writeHead(403,{'Content-Type':'application/json'});return res.end(JSON.stringify({error:'请求来源不受支持'}));
  }
  const url=new URL(req.url,publicOrigin||'http://'+req.headers.host),route=routes[url.pathname];
  if(route){
   const handler=route[req.method];if(!handler){res.writeHead(405);return res.end();}
   const chunks=[];let size=0;const limit=url.pathname==='/api/attachments'?10*1024*1024+16384:2000000;
   for await(const chunk of req){size+=chunk.length;if(size>limit){res.writeHead(413,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'请求内容过大'}));return;}chunks.push(chunk);}
   const headers=new Headers();for(const [key,value] of Object.entries(req.headers))if(value)headers.set(key,Array.isArray(value)?value.join(','):value);
   headers.set('cf-connecting-ip',req.headers['x-real-ip']||req.socket.remoteAddress||'unknown');
   const request=new Request(url,{method:req.method,headers,...(chunks.length?{body:Buffer.concat(chunks)}:{})});
   const result=await handler(request);res.writeHead(result.status,Object.fromEntries(result.headers));res.end(Buffer.from(await result.arrayBuffer()));return;
  }
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405);return res.end();}
  if(url.pathname==='/flow'){res.writeHead(308,{Location:'/flow/'+url.search});return res.end();}
  const name=decodeURIComponent(url.pathname.replace(/^\/flow\//,'/'));
  const target=path.resolve(staticRoot,'.'+(name==='/'?'/index.html':name));
  if(!target.startsWith(staticRoot+path.sep)){res.writeHead(404);return res.end();}
  const info=await stat(target);if(!info.isFile()){res.writeHead(404);return res.end();}
  const cache=target.includes('/assets/')?'public,max-age=31536000,immutable':'no-cache';
  res.writeHead(200,{'Content-Type':mime[path.extname(target)]||'application/octet-stream','Content-Length':info.size,'Cache-Control':cache,'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin'});
  res.end(req.method==='HEAD'?undefined:await readFile(target));
 }catch(e){res.writeHead(e.code==='ENOENT'?404:500,{'Content-Type':'application/json'});res.end(JSON.stringify({error:e.code==='ENOENT'?'未找到页面':'服务暂时不可用'}));if(e.code!=='ENOENT')console.error(e.message);}
});
server.requestTimeout=30000;server.listen(port,host,()=>console.log(`Module collaboration listening on ${host}:${port}`));
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>server.close(()=>{env.DB.close();process.exit(0);}));
