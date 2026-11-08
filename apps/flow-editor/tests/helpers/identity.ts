let email:string|null=null;
export function setIdentity(value:string|null){email=value;}
export async function headers(){return new Headers(email?{'oai-authenticated-user-id':'test-user','oai-authenticated-user-email':email}:{});}
export const env={FLOW_EDITOR_EMAILS:'editor@example.test'};
export function redirect(url:string):never{throw new Error('Redirect: '+url);}
