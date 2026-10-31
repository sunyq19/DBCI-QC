% DBCI-QC adapter: only copies and explicitly selected research measurements.
io = getenv('DBCI_QC_IO');
load(fullfile(io, 'input.mat'));
source_root=getenv('DBCI_QC_SOURCE_ROOT');
wrapper = fileparts(mfilename('fullpath'));
addpath(fullfile(source_root,'signal-1.4.8','inst'));
global dbci_native_pwelch dbci_tapers dbci_taper_eigenvalues dbci_taper_nw;
dbci_native_pwelch = @pwelch;
addpath(fullfile(wrapper,'compat'));
set(0,'defaultfigurevisible','off');
rand('seed',0); randn('seed',0);
engine_version=version;
switch mode
  case 'asr_bursts'
    addpath(fullfile(source_root,'clean_rawdata'));
    state=asr_calibrate(X(:,calibration_first:calibration_last),fs,p.cutoff,10,[],[],p.window_seconds,.66,.1,.25,256);
    M=state.M;T=state.T;A=state.A;B=state.B;
    cleaned=asr_process(X,fs,state,p.window_seconds,0,32,.66,256,false);
    save('-mat7-binary',fullfile(io,'output.mat'),'cleaned','engine_version','M','T','A','B');
  case 'fieldtrip_zvalue'
    addpath(fullfile(source_root,'fieldtrip')); ft_defaults;
    addpath(fullfile(wrapper,'compat'),'-begin');addpath(io,'-begin');
    d=struct('label',{names(:)},'fsample',fs,'trial',{{X}},'time',{{(0:columns(X)-1)/fs}},'sampleinfo',[1 columns(X)]);
    d.chantype=repmat({'unknown'},rows(X),1);d.chanunit=repmat({'V'},rows(X),1);
    cfg=struct('trl',[1 columns(X) 0],'continuous','yes','feedback','no');
    cfg.artfctdef.zvalue=struct('cutoff',p.threshold_z,'channel',{{'all'}},'interactive','no','absdiff','yes',...
      'trlpadding',0,'fltpadding',0,'artpadding',0,'cumulative','no','keepintermediate','yes');
    [configuration,intervals]=ft_artifact_zvalue(cfg,d);
    zvalue=configuration.artfctdef.zvalue.datagui.zmax{1};
    save('-mat7-binary',fullfile(io,'output.mat'),'intervals','zvalue','engine_version');
  case 'cleanline'
    addpath(genpath(fullfile(source_root,'cleanline')));
    addpath(fullfile(source_root,'fieldtrip','external','stats'));
    addpath(fullfile(wrapper,'compat'),'-begin');
    dbci_tapers=tapers;dbci_taper_eigenvalues=taper_eigenvalues;dbci_taper_nw=taper_nw;
    e=struct('data',X,'srate',fs);
    configuration=struct('lineNoiseMethod','clean','lineNoiseChannels',1:rows(X),'Fs',fs,...
      'lineFrequencies',p.line_frequency_hz,'p',p.alpha,'fScanBandWidth',2,'taperBandWidth',2,...
      'taperWindowSize',p.window_seconds,'taperWindowStep',p.step_seconds,'tau',100,'pad',2,...
      'fPassBand',[0 fs/2],'maximumIterations',10);
    [e,configuration]=cleanLineNoise(e,configuration); cleaned=e.data;
    save('-mat7-binary',fullfile(io,'output.mat'),'cleaned','engine_version');
  case 'zapline_plus'
    addpath(fullfile(source_root,'zapline-plus'));
    % Octave requires positional addOptional arguments, unlike the upstream
    % documented named syntax. Keep defaults explicit, no GUI, one fixed chunk.
    [cleaned,configuration,analytics]=clean_data_with_zapline_plus(X,fs,...
      p.line_frequency_hz,1,17,min(99,fs/2-1),6,4,1.76091259055681,1,2,.005,.005,1,3,1,2.5,5,...
      ceil(columns(X)/fs),300,[-.05 .05],[-.4 .1],rows(X),0,100,[0 0 800 600],0,1,30,.95,1);
    save('-mat7-binary',fullfile(io,'output.mat'),'cleaned','configuration','analytics','engine_version');
  otherwise
    error('Unknown method');
end
