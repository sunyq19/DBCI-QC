function varargout=convertStringsToChars(varargin)
% This adapter passes char, numeric, cell and struct, never MATLAB strings.
for k=1:nargin,assert(~isa(varargin{k},'string'));end
varargout=varargin;
end
