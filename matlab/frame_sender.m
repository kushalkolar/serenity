function frame_sender(src, evt, vargin)
    % wrapper function since scanimage only takes 
    % function name strings and not actual objects
    persistent local_sc;
    if isempty(local_sc)
        local_sc = evalin("base", "sc");
    end
    local_sc.new_frame_ready(src);
end
