% Usage
%
% mongo driver
% javaaddpath("C:\Users\scanimage\Documents\scanimage_scripts\mongo-java-driver-3.12.12.jar")
%
% create instance
% mu = MongoUploader('152.19.100.28', 9050)
% 
% to test speed, should be 50Hz with 2 channels at 30Hz each
% mu.speed_test(hSI, 1000)
% 
% set some user function for frame acquired and 
% then do this, it is dumb and wonky but works
% hSI.hUserFunctions.userFunctionsCfg.UserFcnName = mu

classdef MongoUploader
    properties
        mongo_connection
        database
        collection
        wc
    end

    methods
        function obj = MongoUploader(host, port)
            import com.mongodb.*
        
            obj.mongo_connection = com.mongodb.MongoClient(host, port);
            obj.database = obj.mongo_connection.getDB("rt-testing");
            obj.collection = obj.database.getCollection("frames");
            obj.wc = com.mongodb.WriteConcern(1);
          end
    
        function start_acq(obj)
            exp_data = com.mongodb.BasicDBObject();
            exp_data.put("metadata", 0);
            exp_data.put("name", "bah");
            % could update things like min and max vals later
            exp_data.put("max", 0);
            exp_data.put("min", 0);
    
            obj.collection.insert(exp_data, obj.wc);
        end
    
        function send_frame(obj, src, evt, vargin)
            lastStripe = src.hSI.hDisplay.stripeDataBuffer{src.hSI.hDisplay.stripeDataBufferPointer};
            channel = 1;
            frame0 = lastStripe.roiData{1}.imageData{channel}{1}(:);
            frame1 = lastStripe.roiData{1}.imageData{2}{1}(:);
            
            doc = com.mongodb.BasicDBObject();
            
            doc.put("frame0", getByteStreamFromArray(frame0));
            doc.put("frame1", getByteStreamFromArray(frame1));
            doc.put("timestamp", lastStripe.frameTimestamp);
            doc.put("index", lastStripe.frameNumberAcq);
    
            obj.collection.insert(doc, obj.wc);
        end
    
        function speed_test(obj, hSI, n_frames)
            tic
            for i = 1:n_frames
              obj.send_frame(hSI)
            end
            t = toc;
            disp("rate:")
            disp(n_frames / t)
        end
    
       end
end
