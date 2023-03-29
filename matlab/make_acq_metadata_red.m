% gets the scanimage metadata automatically
acq_meta = get_automated_acq_meta(hSI);

% Set these manually per-acquisition
% set acquisition data
acq_meta.database = "/data/kushal/layer1-mesmerize";
acq_meta.animal_id = "mouse_1";

% set red channel data
acq_meta.channels{1}.index = 0; 
acq_meta.channels{1}.name = "l1-interneurons";
acq_meta.channels{1}.indicator = "rcamp";
acq_meta.channels{1}.color = "red";
acq_meta.channels{1}.genotype = "";

% optional comments
acq_meta.comments = "";
