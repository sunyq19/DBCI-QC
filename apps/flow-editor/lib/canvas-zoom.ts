export const MIN_CANVAS_SCALE=.3,MAX_CANVAS_SCALE=1.5;
export const clampScale=(scale:number)=>Math.max(MIN_CANVAS_SCALE,Math.min(MAX_CANVAS_SCALE,scale));
export function wheelPixels(delta:number,mode:number,pageHeight:number){return delta*(mode===1?16:mode===2?pageHeight:1);}
export function wheelScale(scale:number,pixels:number){return clampScale(scale*Math.exp(-Math.max(-240,Math.min(240,pixels))*.002));}
