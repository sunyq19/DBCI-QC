import {createRoot} from 'react-dom/client';
import FlowPage from '../app/flow-page';
import manifest from '../content/sync-manifest.json';
import {publishedSnapshot} from '../lib/flow-loading';
import '../app/globals.css';
createRoot(document.getElementById('root')!).render(<FlowPage published={publishedSnapshot(manifest)}/>);
