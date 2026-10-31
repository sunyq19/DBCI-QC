function [t,e]=dpss(n,nw,k)
% L2 symmetric SciPy DPSS passed by the Python adapter, not an approximation.
global dbci_tapers dbci_taper_eigenvalues dbci_taper_nw;
assert(n==rows(dbci_tapers) && nw==dbci_taper_nw && k==columns(dbci_tapers));
t=dbci_tapers;e=dbci_taper_eigenvalues(:);
end
