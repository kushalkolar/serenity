% Usage
%
% Create SerenityClient instance
% address & port is for the ScanImageReceiver actor on the workstation
% sc = SerenityClient("tcp://152.19.100.28:9050")
% set and run `make_acq_metadata.m`
% prepare acquisition with the `acq_metadata` generated from `make_acq_metadata.m`
% sc.prep_acq(acq_metadata)
% make sure send frames is in UserFunctions, begin grabbing frames
% end acquisition
% sc.end_acq()

classdef SerenityClient
    properties
        context
        socket
        acq_metadata
        acq_ready
        ZMsg
    end

    methods
        function obj = SerenityClient(address)
            % path to jeromq jar file compiled for java8
            % newer java doesn't work on matlab
            jar_path = fullfile(erase(mfilename("fullpath"), mfilename), "/jeromq-0.5.3_java8.jar");
            javaaddpath(jar_path)
            % import zeromq
            import org.zeromq.*;

            % connect to server, client is in PUSH configuration
            obj.context = ZContext();
            obj.socket = obj.context.createSocket(SocketType.PUSH);
            disp(address)
            obj.socket.connect(address);
            obj.acq_ready = false;

            obj.ZMsg = ZMsg;
            disp("Successfully connected!")
        end

        function prep_acq(obj, metadata)
            % prepare acquisition
            obj.socket.send("acquisition-start-incoming");
            acq_meta = jsonencode(metadata);
            obj.socket.send(acq_meta);
            obj.socket.send("acquisition-start-sent");
            % TODO: Would be nice to receive validation response from server
            obj.acq_ready = true;
            disp("Acquisition data sent, check if received on server")
            obj.acq_metadata = metadata;
        end

        function send_frame(obj, src, evt, vargin)
            % sends frame to zmq socket
            % src: hSI object
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
            for channel_ix = last_stripe.roiData{1}.channels
                msg.add(getByteStreamFromArray(last_stripe.roiData{1}.imageData{channel_ix}{1}(:)));
            end

            % send
            msg.send(obj.socket);
        end

        function end_acq(obj)
            obj.acq_ready = false;
            obj.socket.send("acquisition-end")
            disp("Acquisition ended")
        end

        function speed_test(obj, src, n_frames)
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
