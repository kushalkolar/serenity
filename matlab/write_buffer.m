function write_buffer(buffer_path, last_stripe, current_frame_ix, sub_session)
    % write frame to buffer on disk
    % frame index within this scanimage grab
    sub_frame_index = getByteStreamFromArray(uint32(last_stripe.frameNumberAcq));

    % frame index within this acquisition
    frame_ix = getByteStreamFromArray(uint32(current_frame_ix));

    % sub session index
    sub_session_ix = getByteStreamFromArray(uint32(sub_session));
    
    fname = strcat(num2str(last_stripe.frameNumberAcq), ".bin");
    fid = fopen(fullfile(buffer_path, fname), "w");

    fwrite(fid, frame_ix);
    fwrite(fid, sub_frame_index);
    fwrite(fid, sub_session_ix);

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
