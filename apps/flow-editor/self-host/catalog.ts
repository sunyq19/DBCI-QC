import bundled from '../content/sync-manifest.json';
import {validateManifest} from '../lib/sync';
// The release carries the QC catalogue. Updating a release merges it into the
// editable head; team notes and immutable versions are preserved by syncCatalog.
const manifest=validateManifest(bundled);
export const readCatalog=()=>manifest;
export const catalogStatus=()=>({sequence:bundled.sequence,source:'deployment'});
