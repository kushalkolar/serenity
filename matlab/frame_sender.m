% This is slow af with MongoDB because matlab is terrible
% also because the computer is ancient
% But gives an idea of how to make a class for sending stuff

classdef FrameSender
   properties
        mc
        db
        coll
        wc
   end
   methods
      function obj = FrameSender(host, port)
         import com.mongodb.*

         obj.mc = com.mongodb.MongoClient(host, port);
         obj.db = obj.mc.getDB("rt-testing");
         obj.coll = obj.db.getCollection("frames");
         obj.wc = com.mongodb.WriteConcern(1);
      end
      function send(obj, src, evt, vargin)
          lastStripe = src.hSI.hDisplay.stripeDataBuffer{src.hSI.hDisplay.stripeDataBufferPointer};

          doc = com.mongodb.BasicDBObject();

          doc.put("data", jsonencode(lastStripe.roiData{1}.imageData{1}{1}));
          doc.put("index", lastStripe.frameNumberAcq);

          obj.coll.insert(doc, obj.wc);
      end
   end
end
