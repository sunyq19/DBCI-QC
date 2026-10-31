function [p,f]=pwelch(x,w,overlap,nfft,fs)
% Only the five-argument call used by pinned Zapline-plus is supported.
% Match MATLAB column-wise Welch: half overlap, no detrend, power density,
% nfft=max(256,nextpow2(window)). Delegate numeric work to Octave signal.
global dbci_native_pwelch;
assert(nargin==5 && isvector(w) && isempty(overlap) && isempty(nfft));
nfft=max(256,2^nextpow2(length(w)));
if isvector(x),x=x(:);end
for c=1:columns(x)
 [p(:,c),f]=dbci_native_pwelch(x(:,c),w,floor(length(w)/2)/length(w),nfft,fs,'onesided','none');
end
end
