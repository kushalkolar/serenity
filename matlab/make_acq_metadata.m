acq_metadata = struct();
acq_metadata.framerate = hSI.hRoiManager.scanFrameRate;
acq_metadata.date = datestr(now, "yyyymmdd-HHMMSS");

n_channels = max(hSI.hChannels.channelsActive);
channel_metadata = cell(n_channels, 1);

for i = 1:n_channels
    channel_metadata{i} = struct();
    n_rows = hSI.hRoiManager.linesPerFrame;
    n_cols = hSI.hRoiManager.pixelsPerLine;
    channel_metadata{i}.shape = [n_rows, n_cols];
    channel_metadata{i}.dtype = hSI.hScan2D.channelsDataType;
end

% set channel data
channel_metadata{1}.index = 0;
channel_metadata{1}.name = "axons";
channel_metadata{1}.indicator = "gcamp8f";
channel_metadata{1}.color = "green";
channel_metadata{1}.genotype = "necab-gcamp8f";

channel_metadata{2}.index = 1;
channel_metadata{2}.name = "l1-interneurons";
channel_metadata{2}.indicator = "rcamp";
channel_metadata{2}.color = "red";
channel_metadata{2}.genotype = "";

% set acquisition data
acq_metadata.database = "/data/kushal/layer1-mesmerize";
acq_metadata.animal_id = "mouse_1";
acq_metadata.channels = channel_metadata;
