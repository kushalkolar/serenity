% gets the scanimage metadata automatically
acq_meta = get_automated_acq_meta(hSI);

% Set these manually per-acquisition
% set acquisition data

%%
% *BOLD TEXT* 
acq_meta.database = "/data/kushal/layer1-db/batch.h5";
acq_meta.animal_id = "mouse_1";

% set green channel data
acq_meta.channels{1}.index = 0;
acq_meta.channels{1}.name = "va-axons";
acq_meta.channels{1}.indicator = "gcamp8f";
acq_meta.channels{1}.color = "green";
acq_meta.channels{1}.genotype = "necab-gcamp8f+aav-syn-flex-gcamp8f";

% set red channel data
acq_meta.channels{2}.index = 1; 
acq_meta.channels{2}.name = "pyr-dendrites";
acq_meta.channels{2}.indicator = "rcamp";
acq_meta.channels{2}.color = "red";
acq_meta.channels{2}.genotype = "retro-aav-sl1-cag-rcamp1b";

% this sub session
acq_meta.sub_session = 0;

% optional comments
acq_meta.comments = "";


clear frame_sender
clear write_buffer
sc = SerenityClient("tcp://127.0.0.1:9005", "C:/Users/scanimage/serenity_buffer");
sc.prep_acq(acq_meta)
hSI.startGrab()
