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
          channel = 1;
          frame0 = lastStripe.roiData{1}.imageData{channel}{1}(:);
          frame1 = lastStripe.roiData{1}.imageData{2}{1}(:);

          doc = com.mongodb.BasicDBObject();

          doc.put("frame0", getByteStreamFromArray(frame0));
          doc.put("frame1", getByteStreamFromArray(frame1));
          %doc.put("timestamp", num2str(lastStripe.frameTimestamp));
          doc.put("index", lastStripe.frameNumberAcq);

          obj.coll.insert(doc, obj.wc);
      end
   end
end
