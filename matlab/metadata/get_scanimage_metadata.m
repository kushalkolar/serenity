function meta = get_scanimage_metadata(hsi)
    % get relevant metadata from hSI object
    meta = struct();

    % the "main" fields directly under hSI
    main_fields = fieldnames(hsi);
    for i = 1:numel(main_fields)
        % keep only native types, not scanimage objects
        kind = class(hsi.(main_fields{i}));

            % set metadata field only if it's not a scanimage object
            if ~contains(kind, ".")
                meta.(main_fields{i}) = hsi.(main_fields{i});
            end
    end

    % all other metadata
    meta_fields = {
        "hRoiManager",
        "hBeams",
        "hMotors",
        "hChannels",
        "hShutters",
        "hDisplay",
        "hUserFunctions",
        "hScan2D",
        "hStackManager"  % this contains info such as how many frames the user has set to capture
    };

    % each meta data field
    for i = 1:numel(meta_fields)
        s = struct();
        % get the all the field names under this
        sub_fields = fieldnames(hsi.(meta_fields{i}));

        for j = 1:numel(sub_fields)
            % keep only native types, don't keep scanimage objects
            % scanimage objects contain interfaces to the hardware etc.
            % does not make sense to serialize hardware objects
            kind = class(hsi.(meta_fields{i}).(sub_fields{j}));

            % set metadata field only if it's not a scanimage object
            if ~contains(kind, ".")
                s.(sub_fields{j}) = hsi.(meta_fields{i}).(sub_fields{j});
            end
        end

        % set the meta data field
        meta.(meta_fields{i}) = s;
    end

    % remove some non-serializable objects
    meta.hBeams = rmfield(meta.hBeams, "pzFunction ");
    meta.hBeams = rmfield(meta.hBeams, "hBeams");

    % remove last frame data since this is not necessary
    meta.hDisplay = rmfield(meta.hDisplay, "lastFrame");
    meta.hDisplay = rmfield(meta.hDisplay, "lastAveragedFrame");
    
    % remove shutter data for now 
    % contains lots of non-serializable hardware objcs
    meta.hShutters = rmfield(meta.hShutters, "hShutters");
end
