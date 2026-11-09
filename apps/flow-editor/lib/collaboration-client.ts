const KEY='dbci-flow-edit-session';
export function clearLegacyLink(){sessionStorage.removeItem('dbci-flow-edit-link');if(new URLSearchParams(location.hash.slice(1)).has('edit'))history.replaceState(null,'',location.pathname+location.search);}
export function saveEditorSession(token:string){sessionStorage.setItem(KEY,token);}
export function editorHeaders():Record<string,string>{const token=sessionStorage.getItem(KEY);return token?{'X-Flow-Editor':token}:{};}
export function forgetEditor(){sessionStorage.removeItem(KEY);}
