function write_buffer(buffer_path, last_stripe)
    persistent ard
    if isempty(ard)
        ard = evalin("base", "ard_device");
    end
    persistent trigger_val
    if isempty(trigger_val)
        trigger_val = 0;
    end

    % write frame to buffer on disk
    % frame index
    ix = last_stripe.frameNumberAcq;
    
    fid = fopen(fullfile(buffer_path, strcat(num2str(ix), ".bin")), "w");
    
    % write frame index
    fwrite(fid, getByteStreamFromArray(uint32(ix)));

    % trial index
    fwrite(fid, getByteStreamFromArray(uint32(0)));
    % trigger state
    state = fgetl(ard);  % as a string

    % in case empty character array because matlab is weird
    if isempty(state)
        % just use previous state
        state = trigger_val;
    end
    
    % use last character of in case it's like '00' because matlab is weird
    % in reading serial
    trigger_val = state;
    fwrite(fid, getByteStreamFromArray(uint32(str2double(state(end)))));
    %fwrite(fid, getByteStreamFromArray(uint32(0)));
    % timestamp
    fwrite(fid, getByteStreamFromArray(single(last_stripe.frameTimestamp)));

    % frame data
    for channel_ix = 1:length(last_stripe.roiData{1}.channels)
        fwrite(fid, getByteStreamFromArray(last_stripe.roiData{1}.imageData{channel_ix}{1}(:)));
    end

    fclose(fid);

    % signal that frame buffer is ready to be read
    fid = fopen(fullfile(buffer_path, strcat(num2str(ix), ".done")), "w");
    fclose(fid);
end