function rval = get_automated_acq_meta(hsi)
    % makes some of the acq meta data automatically
    rval = struct();
    rval.framerate = hsi.hRoiManager.scanFrameRate;
    rval.date = datestr(now, "yyyymmdd-HHMMSS");
    % the scanimage state
    rval.scanimage_meta = get_scanimage_metadata(hsi);
    
    n_channels = length(hsi.hChannels.channelsActive);
    channel_metadata = cell(n_channels, 1);
    
    for i = 1:n_channels
        channel_metadata{i} = struct();
        n_rows = hsi.hRoiManager.linesPerFrame;
        n_cols = hsi.hRoiManager.pixelsPerLine;
        channel_metadata{i}.shape = [n_rows, n_cols];
        channel_metadata{i}.dtype = hsi.hScan2D.channelsDataType;
    end
    rval.channels = channel_metadata;
end
