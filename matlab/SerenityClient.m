% zmq client to communicate with improv ScanImageReceiver actor
% 
% Usage
% Make sure "serenity/matlab" is in the matlab path
% 
% Create SerenityClient instance
% sc = SerenityClient("tcp://hantman-workstation:9050")
%
% setup acquisition metadata
% set and run `make_acq_metadata.m`
% prepare acquisition with the `acq_metadata` generated from `make_acq_metadata.m`
% sc.prep_acq(acq_metadata)
%
% make sure serenity_frame_sender is in UserFunctions, begin grabbing frames
%
% end acquisition
% sc.end_acq()

classdef SerenityClient < handle
    properties
        context
        socket
        acq_metadata
        acq_ready
        ZMsg
        parent_buffer_path
        current_buffer_path
        bg_pool
    end

    properties(SetAccess=protected, GetAccess=public)
        address
    end

    methods
        function obj = SerenityClient(address, parent_buffer_path)
            % address: tcp address and port of server
            % example: tcp://152.19.100.28:9050
            
            % path to jeromq jar file compiled for java8
            % newer java doesn't work on matlab
            jar_path = fullfile(erase(mfilename("fullpath"), mfilename), "/jeromq-0.5.3_java8.jar");
            javaaddpath(jar_path)
            % import zeromq
            import org.zeromq.*;

            % connect to server, client is in PUSH configuration
            obj.context = ZContext();
            obj.socket = obj.context.createSocket(SocketType.PUSH);
            obj.socket.connect(address);
            obj.acq_ready = false;

            obj.ZMsg = ZMsg;
            disp("Successfully connected!")
            obj.address = address;
            disp(obj.address)

            obj.parent_buffer_path = parent_buffer_path;
            obj.current_buffer_path = "";
        end

        function prep_acq(obj, metadata)
            % prepare acquisition
            obj.socket.send("acquisition-prep-incoming");
            acq_meta = jsonencode(metadata);
            obj.socket.send(acq_meta);
            obj.socket.send("acquisition-prep-sent");
            % TODO: Would be nice to receive validation response from server
            obj.acq_ready = true;
            disp("Acquisition data sent, check if received on server")
            obj.acq_metadata = metadata;
            obj.current_buffer_path = fullfile(obj.parent_buffer_path, "test");
            mkdir(obj.current_buffer_path)
        end

        function send_frame(obj, src)
            % sends frame to zmq socket
            % src: scanimage hSI object

%             if obj.acq_ready ~= true
%                 ex = MException("Acquisition is not preped. Call pre_acq() first.");
%                 throw(ex)
%             end
            % get data from scanimage
            last_stripe = src.hSI.hDisplay.stripeDataBuffer{src.hSI.hDisplay.stripeDataBufferPointer};

            msg = obj.ZMsg();
            % frame index
            msg.add(getByteStreamFromArray(uint32(last_stripe.frameNumberAcq)));
            % trial index
            msg.add(getByteStreamFromArray(uint32(0)));
            % trigger state
            msg.add(getByteStreamFromArray(uint32(0)));
            % timestamp
            msg.add(getByteStreamFromArray(single(last_stripe.frameTimestamp)));

            % frame data
            for channel_ix = 1:length(last_stripe.roiData{1}.channels)
                msg.add(getByteStreamFromArray(last_stripe.roiData{1}.imageData{channel_ix}{1}(:)));
            end

            % send
            msg.send(obj.socket);
        end
        
        function new_frame_ready(obj, src)
            last_stripe = src.hSI.hDisplay.stripeDataBuffer{src.hSI.hDisplay.stripeDataBufferPointer};
            parfeval(backgroundPool, @obj.write_buffer, 0, last_stripe)
        end

        function write_buffer(obj, last_stripe)
            % write frame to buffer on disk
            % frame index
            frame_index = getByteStreamFromArray(uint32(last_stripe.frameNumberAcq));
            
            fname = strcat(num2str(last_stripe.frameNumberAcq), ".bin");
            fid = fopen(fullfile(obj.current_buffer_path, fname), "w");

            fwrite(fid, frame_index)

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

        function end_acq(obj)
            obj.acq_ready = false;
            obj.socket.send("acquisition-end")
            disp("Acquisition ended")
        end

        function speed_test(obj, src, n_frames)
                % srs: scanimage hSI object
                % n_frames: number of frames to send
            tic;
            for i = 1:n_frames
                obj.send_frame(src);
            end
            t = toc;
            disp("rate: ")
            disp(n_frames / t)
        end
    end
end
