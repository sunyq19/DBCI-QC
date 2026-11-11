import {createInterface} from 'node:readline/promises';
import {Writable} from 'node:stream';
import {randomBytes,pbkdf2Sync} from 'node:crypto';
import {writeFileSync,existsSync} from 'node:fs';
const file='/config/password.verifier';
if(!process.stdin.isTTY)throw new Error('请在交互终端中输入密码。');
if(existsSync(file))throw new Error('编辑密码已配置；此命令不会覆盖。');
// Prompts are printed explicitly; readline receives a muted output stream.
const hidden=new Writable({write(_chunk,_encoding,next){next();}});
const terminal=createInterface({input:process.stdin,output:hidden,terminal:true});
try{
 process.stdout.write('编辑密码：');const first=await terminal.question('');
 process.stdout.write('\n再次输入：');const second=await terminal.question('');process.stdout.write('\n');
 if(!first||first.length>256||first!==second)throw new Error('两次密码须一致，长度为 1–256 字符。');
 const salt=randomBytes(16),digest=pbkdf2Sync(first,salt,100000,32,'sha256');
 writeFileSync(file,`pbkdf2:100000:${salt.toString('hex')}:${digest.toString('hex')}\n`,{flag:'wx',mode:0o600});
 process.stdout.write('已保存密码校验值。\n');
}finally{terminal.close();}
