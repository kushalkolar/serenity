function write_buffer(buffer_path, last_stripe)
    persistent ard
    if isempty(ard)
        ard = evalin("base", "ard_device");
    end

    % write frame to buffer on disk
    % frame index
    ix = last_stripe.frameNumberAcq;
    
    fname = strcat(num2str(ix), ".bin");
    fid = fopen(fullfile(buffer_path, fname), "w");
    
    % write frame index
    fwrite(fid, getByteStreamFromArray(uint32(ix)));

    % trial index
    fwrite(fid, getByteStreamFromArray(uint32(0)));
    % trigger state
    fwrite(fid, getByteStreamFromArray(uint32(fread(ard))));
    % timestamp
    fwrite(fid, getByteStreamFromArray(single(last_stripe.frameTimestamp)));

    % frame data
    for channel_ix = 1:length(last_stripe.roiData{1}.channels)
        fwrite(fid, getByteStreamFromArray(last_stripe.roiData{1}.imageData{channel_ix}{1}(:)));
    end

    fclose(fid);
end