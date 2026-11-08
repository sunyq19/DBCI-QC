import navigation from '../config/navigation.json';

/** Preserve existing version/history shares without accepting redirect targets. */
export function flowUrlForLegacyLink(address:string):string {
  const previous=new URL(address);
  const target=new URL(navigation.flowUrl);
  const version=previous.searchParams.get('version');
  const revision=previous.searchParams.get('revision');
  if(version)target.searchParams.set('version',version);
  else if(revision)target.searchParams.set('revision',revision);
  target.hash=previous.hash;
  return target.href;
}
