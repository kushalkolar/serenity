# serenity

Basically `improv` + `mesmerize` + `fastplotlib` for realtime analysis and visualization of calcium imaging and behavior data.

WIP

## Installation

### Install zmq in matlab

Build [`jeromq`](https://github.com/zeromq/jeromq) using maven on linux and use the jar file on matlab in Windows. I was not able to build on windows.

1. Install OpenJDK 8 on linux. Newer versions of Java beyond v8 do not work in matlab! asically just unpack this tar.gz file and then export the unpacked path as `JAVA_HOME` and set the `PATH` to the `bin` dir, and `LD_LIBRARY_PATH` to the `lib` dir: https://adoptium.net/temurin/releases/ 

2. Install maven and make sure it binds to java 8: https://dlcdn.apache.org/maven/maven-3/3.9.1/binaries/apache-maven-3.9.1-bin.zip

```sh
export JAVA_HOME=...
export PATH=...
sudo apt install maven
mvn --version
```

Should return:

```sh
Apache Maven 3.6.3
Maven home: /usr/share/maven
Java version: 1.8.0_362, vendor: Temurin, runtime: /home/kushalk/Downloads/jdk8u362-b09/jre
Default locale: en_US, platform encoding: UTF-8
OS name: "linux", version: "5.10.0-21-amd64", arch: "amd64", family: "unix"
```

3. Build `jeromq`

```sh
cd ~/repos
git clone https://github.com/zeromq/jeromq.git

# checkout v0.5.3
git checkout v0.5.3

# build jar
mvn package
```

4. Copy jar file to scanimage computer

```sh
scp kushalk@hantman-calcium:/home/kushalk/repos/jeromq/target/jeromq-0.5.3.jar ..
```

To test:

Start server in python on receiving computer:

```python
import zmq

context = zmq.Context()
sub = context.socket(zmq.PULL)
sub.bind("tcp://0.0.0.0:9050")
sub.recv()

# should receive
Out[5]: b'yay'
```

Start client on matlab and send:

```matlab
javaaddpath('C:\Users\scanimage\jeromq-0.5.3_java8.jar')
import org.zeromq.*

context = ZContext()
socket = context.createSocket(SocketType.PUSH)
socket.connect("tcp://152.19.100.28:9050")
socket.send("yay")
```

Benchmarking, send random frames from matlab:

```matlab
t0 = clock();
for i = 1:2000
  a = int16(randi(512, 512));
  socket.send(getByteStreamFromArray(a));
end
clock() - t0
```

This gives ~6.4 seconds, or ~300 frames/s

```python
l = list()
while True:
    t0 = time()
    b = sub.recv()
    l.append(time() - t0)
```

This results in a median delay of ~0.0044 s between frames, or ~225 frames/second, which is just below the theoretical max of 238 for a 1 gigabit connection since 125 MB / (512 * 512 * 2) = 238. 125MB = 1 gigabit.
