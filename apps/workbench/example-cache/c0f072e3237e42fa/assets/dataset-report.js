'use strict';
document.getElementById('print-report')?.addEventListener('click',()=>window.print());
// Include score provenance in browser PDF/print, then restore the reader's view.
let printScoreDetails = [];
window.addEventListener('beforeprint', () => {
  printScoreDetails = [];
  document.querySelectorAll('details.score-component').forEach(component => {
    for (let element = component; element; element = element.parentElement) {
      if (element.tagName === 'DETAILS' && !element.open) {
        printScoreDetails.push(element);
        element.open = true;
      }
    }
  });
});
window.addEventListener('afterprint', () => {
  printScoreDetails.reverse().forEach(element => { element.open = false; });
  printScoreDetails = [];
});
