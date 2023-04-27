function write_buffer(buffer_path, last_stripe)
    % write frame to buffer on disk
    % frame index
    frame_index = getByteStreamFromArray(uint32(last_stripe.frameNumberAcq));
    
    fname = strcat(num2str(last_stripe.frameNumberAcq), ".bin");
    fid = fopen(fullfile(buffer_path, fname), "w");

    fwrite(fid, frame_index);

    % trial index
    fwrite(fid, getByteStreamFromArray(uint32(0)));
    % trigger state
    fwrite(fid, getByteStreamFromArray(uint32(0)));
    % timestamp
    fwrite(fid, getByteStreamFromArray(single(last_stripe.frameTimestamp)));

    % frame data
    for channel_ix = 1:length(last_stripe.roiData{1}.channels)
        fwrite(fid, getByteStreamFromArray(last_stripe.roiData{1}.imageData{channel_ix}{1}(:)));
    end

    fclose(fid);
end