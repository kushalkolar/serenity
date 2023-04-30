int trigger_pin = 38;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
  pinMode(trigger_pin, INPUT);
}

void loop() {
  // put your main code here, to run repeatedly:
  //delayMicroseconds(1);
  int trigger_state = digitalRead(trigger_pin);
  Serial.print(trigger_state);
  Serial.print("\n");
}
