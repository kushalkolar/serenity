function serenity_frame_sender(src, evt, vargin)
    % wrapper function since scanimage only takes 
    % function name strings and not actual objects
    persistent local_sc;
    local_sc = evalin("base", "sc");
    local_sc.send_frame(src);
end
