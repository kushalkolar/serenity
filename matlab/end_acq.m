function end_acq(src, evt, vargin)
    persistent local_sc;
    if isempty(local_sc)
        local_sc = evalin("base", "sc");
    end
    local_sc.end_acq(src);
end