import { env } from 'cloudflare:workers';
import { getChatGPTUser } from '../../chatgpt-auth';
import { isEditor } from '../../../lib/flow';
export const dynamic='force-dynamic';
export async function GET(){const user=await getChatGPTUser();return Response.json({signedIn:!!user,canEdit:!!user&&isEditor(user.email,env.FLOW_EDITOR_EMAILS),email:user?.email??null},{headers:{'Cache-Control':'private, no-store','Vary':'Cookie'}});}
