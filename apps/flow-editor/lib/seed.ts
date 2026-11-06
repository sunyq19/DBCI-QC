import initial from '../content/initial-flow.json';
import { validateDoc } from './flow';
export const seed = validateDoc(initial);
