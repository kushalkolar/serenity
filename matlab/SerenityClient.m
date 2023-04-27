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
        uid
        parent_buffer_path
        current_buffer_path
        ZMQ_NOBLOCK
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

            obj.ZMQ_NOBLOCK = ZMQ.NOBLOCK;

            % connect to server, client is in PUSH configuration
            obj.context = ZContext();
            obj.socket = obj.context.createSocket(SocketType.REQ);
            obj.socket.connect(address);

            obj.acq_ready = false;
            obj.uid = "";

            disp("Successfully connected!")
            obj.address = address;

            obj.parent_buffer_path = parent_buffer_path;
            obj.current_buffer_path = "";
        end

        function prep_acq(obj, metadata)
            % prepare acquisition
            % get acq metadata
            acq_meta = jsonencode(metadata);

            % send to serenity server
            obj.socket.send(acq_meta);
            tic;
            % wait for server to acknowledge
            while true
                reply = obj.socket.recv(obj.ZMQ_NOBLOCK);
                if toc > 10
                    error("Timeout exceeded for confirming acquisition start")
                end
                % reply not yet received, try again
                if isempty(reply)
                    % wait for 0.5s
                    pause(0.5)
                    continue
                end
                % get string representation from bytes
                response = convertCharsToStrings(native2unicode(reply));
                % if there was a failure
                if startsWith(response, "Failed")
                    error(response)
                else
                    % uuid of this acquisition
                    obj.uid = response;
                    % ready for acquisition
                    obj.acq_ready = true;
                    % acq metadata
                    obj.acq_metadata = metadata;
                    % make path for frame buffer
                    obj.current_buffer_path = fullfile(obj.parent_buffer_path, obj.uid);
                    mkdir(obj.current_buffer_path)

                    disp("Acquisition prepped successfully with uid:")
                    disp(obj.uid)
                    break
                end
            end
        end
        
        function new_frame_ready(obj, src)
            last_stripe = src.hSI.hDisplay.stripeDataBuffer{src.hSI.hDisplay.stripeDataBufferPointer};
            %parfeval(obj.pool, @write_buffer, 0, obj.current_buffer_path, last_stripe);
            write_buffer(obj.current_buffer_path, last_stripe)
        end

        function end_acq(obj, src)
            obj.acq_ready = false;
            obj.uid = "";

            last_stripe = src.hSI.hDisplay.stripeDataBuffer{src.hSI.hDisplay.stripeDataBufferPointer};
            frame_index = getByteStreamFromArray(uint32(last_stripe.frameNumberAcq));

            % get index of last frame
            obj.socket.send(frame_index)

            % wait for serenity server to end acq
            tic;
            % wait for server to acknowledge
            while true
                reply = obj.socket.recv(obj.ZMQ_NOBLOCK);
                if toc > 30
                    error("Timeout exceeded for confirming acquisition end")
                    break
                end
                if isempty(reply)
                    pause(0.5)
                    continue
                end
                response = convertCharsToStrings(native2unicode(reply));
                disp(response)
                % reset
                obj.acq_ready = false;
                obj.uid = "";
                obj.acq_metadata = "";
            end
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
