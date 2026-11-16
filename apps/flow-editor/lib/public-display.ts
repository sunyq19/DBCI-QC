/** Project attribution for public display, including existing fixed versions.
 * Stored discussions remain unchanged; the returned hash describes the displayed doc.
 */
export async function publicDisplay(value: unknown): Promise<unknown> {
  const raw = JSON.stringify(value);
  const text = raw
    .replace(/\u96f7\u4f73\u6b23(?: \/ BrainElecQC)?/g, 'BrainElecQC')
    .replace(/Jiaxin\s+Lei(?: \/ BrainElecQC)?/gi, 'BrainElecQC');
  if (text === raw) return value;
  const result = JSON.parse(text);
  if (result.doc && typeof result.hash === 'string') {
    const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(result.doc)));
    result.hash = Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');
  }
  result.displayPolicy = 'project-attribution/1';
  return result;
}
