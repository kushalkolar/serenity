% gets the scanimage metadata automatically
acq_meta = get_automated_acq_meta(hSI);

% Set these manually per-acquisition
% set acquisition data

%%
% *BOLD TEXT* 
acq_meta.database = "/data/kushal/layer1-db/batch.parquet";
acq_meta.animal_id = "mouse_1";

% set green channel data
acq_meta.channels{1}.index = 0;
acq_meta.channels{1}.name = "axons";
acq_meta.channels{1}.indicator = "gcamp8f";
acq_meta.channels{1}.color = "green";
acq_meta.channels{1}.genotype = "necab-gcamp8f";

% set red channel data
acq_meta.channels{2}.index = 1; 
acq_meta.channels{2}.name = "l1-interneurons";
acq_meta.channels{2}.indicator = "rcamp";
acq_meta.channels{2}.color = "red";
acq_meta.channels{2}.genotype = "";

% optional comments
acq_meta.comments = "";

% Set sub-session between every table-round!
acq_meta.sub_session = 1;
