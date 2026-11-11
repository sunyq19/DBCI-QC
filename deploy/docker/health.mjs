import http from 'node:http';
const request=http.get({hostname:'127.0.0.1',port:18770,path:'/api/flow?head=1',headers:{Host:new URL(process.env.FLOW_PUBLIC_ORIGIN).host}},response=>{
 let body='';response.on('data',chunk=>{body+=chunk;});response.on('end',()=>{try{if(response.statusCode!==200||!JSON.parse(body).latestRevision)process.exit(1);}catch{process.exit(1);}});
});
request.setTimeout(4000,()=>{request.destroy();process.exit(1);});request.on('error',()=>process.exit(1));
