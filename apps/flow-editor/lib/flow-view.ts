import {displayNodes,drawingEdges,flattenNodes,type FlowDoc,type FlowNode} from './flow';

export const FLOW_FILTERS=[['all','全部模块'],['eeg','头皮 EEG'],['ecog','ECoG'],['seeg','sEEG'],['np','Neuropixels'],['dataset','数据集']] as const;

// A view projection only: never save the filtered tree back into a draft.
export function filterFlow(doc:FlowDoc,scope:string):FlowDoc {
 function prune(nodes:FlowNode[]):FlowNode[]{
  return nodes.flatMap(node=>{
   const children=node.children?prune(node.children):undefined;
   return scope==='all'||node.scope.includes(scope)||children?.length?[{...node,children}]:[];
  });
 }
 const nodes=prune(displayNodes(doc.nodes)),ids=new Set(flattenNodes(nodes).map(n=>n.id));
 const visible=(edge:FlowDoc['edges'][number])=>ids.has(edge.source)&&ids.has(edge.target);
 return {...doc,nodes,edges:doc.edges.filter(visible),drawing:{edges:drawingEdges(doc).filter(visible)}};
}
