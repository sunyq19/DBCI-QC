import React from 'react';
import {createRoot} from 'react-dom/client';
import FlowPage from '../app/page';
import {validateDoc} from '../lib/flow';
import publication from '../content/releases/publication.json';
import '../app/globals.css';
for(const release of publication.releases)validateDoc(release.doc);
window.__FLOW_PUBLICATION__=publication as import('../lib/static-reader').Publication;
createRoot(document.getElementById('root')!).render(<FlowPage/>);
