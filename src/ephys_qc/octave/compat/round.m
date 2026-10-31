function y=round(x,n)
% Zapline-plus uses round(x,2) for diagnostic text only.
if nargin==1,y=builtin('round',x);else,y=builtin('round',x.*10.^n)./10.^n;end
end
