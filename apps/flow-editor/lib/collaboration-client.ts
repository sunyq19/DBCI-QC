const KEY='dbci-flow-edit-link';
export function consumeEditorLink(){
 const params=new URLSearchParams(location.hash.slice(1));if(!params.has('edit'))return;
 const token=params.get('edit')||'';
 history.replaceState(null,'',location.pathname+location.search);
 if(!/^[A-Za-z0-9_-]{43}$/.test(token))throw new Error('编辑链接格式不正确');
 sessionStorage.setItem(KEY,token);
}
export function editorHeaders():Record<string,string>{const token=sessionStorage.getItem(KEY);return token?{'X-Flow-Editor':token}:{};}
export function forgetEditor(){sessionStorage.removeItem(KEY);}
export function acceptEditorLink(input:string,base:string){const url=new URL(input);if(url.origin!==new URL(base).origin||url.pathname!==new URL(base).pathname)throw new Error('请使用本模块协作页的成员编辑链接');const token=new URLSearchParams(url.hash.slice(1)).get('edit')||'';if(!/^[A-Za-z0-9_-]{43}$/.test(token))throw new Error('编辑链接格式不正确');sessionStorage.setItem(KEY,token);}
