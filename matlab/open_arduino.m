ard_device = serial("COM5");
ard_device.InputBufferSize = 6;
ard_device.ReadAsyncMode = "manual";
ard_device.Terminator = "LF";
fopen(ard_device);
