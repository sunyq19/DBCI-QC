import {flowUrlForLegacyLink} from '../lib/navigation';

const target=flowUrlForLegacyLink(window.location.href);
const link=document.getElementById('continue-link');
if(link instanceof HTMLAnchorElement)link.href=target;
window.location.replace(target);
