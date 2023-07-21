import sys
from hashlib import sha256 as sha

ns.cppyy.cppdef("""
    #ifndef StreamingAppSendBlock
    #define StreamingAppSendBlock
    namespace ns3
    {
        EventImpl* pythonMakeEventSendBlock(void (*f)(Ptr<Socket>, Address&), Ptr<Socket> socket, Address address)
        {
            return MakeEvent(f, socket, address);
        }
    }
    #endif
""")


class StreamingServer(ns.applications.Application):
    LOGGING = True
    STREAMING_PORT = 2345  # 默认的应用监听端口
    socketToInstanceDict = {}

    def __init__(self, node, port=STREAMING_PORT, text_file=None):
        if not text_file:
            raise Exception("未指定文本文件")
        import os
        if not os.path.exists(text_file):
            raise Exception("文件不存在", text_file)
        super().__init__()  # 调用ns.Application的构造函数
        self.__python_owns__ = False  # 允许C++在Simulator::Destroy调用时销毁该对象
        self.port = port  # 服务器监听端口
        # 创建一个UDP套接字
        self.m_socket = ns.network.Socket.CreateSocket(
            node, ns.core.TypeId.LookupByName("ns3::UdpSocketFactory"))
        # 将套接字绑定到特定的端口和IP地址上进行监听
        self.m_socket.Bind(ns.network.InetSocketAddress(
            ns.network.Ipv4Address.GetAny(), self.port).ConvertTo())
        # 创建用于处理接收到的数据包的回调函数，使用StreamingServer类的静态函数
        # (这是为了让应用程序从Python中正常工作的一种解决方法)
        self.m_socket.SetRecvCallback(
            ns.make_rx_callback(StreamingServer._Receive))
        # 将套接字注册为字典的键，并将其关联到该应用程序实例
        StreamingServer.socketToInstanceDict[self.m_socket] = self

        # 加载文本文件并将其分块
        self.text_chunks = self.load_text_chunks(text_file)

    def __del__(self):
        # 当对象销毁时，从字典中删除实例条目
        del StreamingServer.socketToInstanceDict[self.m_socket]

    def load_text_chunks(self, text_file):
        # 加载文本文件并将其分块
        text_chunks = []
        with open(text_file, 'r') as file:
            chunk_size = 1000  # 假设每个文本块的大小为1000个字符
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                text_chunks.append(chunk)
        return text_chunks

    def send_block(self, address):
        # 检查待发送的块列表是否已结束
        if len(self.text_chunks) == 0:
            return

        # 获取一个块并发送
        block_to_transmit = self.text_chunks[0]
        self.text_chunks.pop(0)
        # print("发送", sha(block_to_transmit.encode()).hexdigest())
        # 将字符串转换为字节流，并创建一个ns-3数据包
        packet_with_stream_block = ns.network.Packet(
            block_to_transmit.encode(), len(block_to_transmit))
        packet_with_stream_block.__python_owns__ = False

        self.send(packet_with_stream_block, address)

        # 直到块列表耗尽后重新安排事件
        event = ns.pythonMakeEventSendBlock(
            self._send_block, self.m_socket, address)
        ns.core.Simulator.Schedule(ns.core.MilliSeconds(60), event)

    def send(self, packet, address):
        # 将数据包发送到目标地址
        self.m_socket.SendTo(packet, 0, address)
        if StreamingServer.LOGGING:
            inetAddress = ns.network.InetSocketAddress.ConvertFrom(address)
            print("在时间+{s}秒，服务器从{ip}端口{port}发送了{b}字节"
                  .format(s=ns.core.Simulator.Now().GetSeconds(),
                          ip=inetAddress.GetIpv4(),
                          port=inetAddress.GetPort(),
                          b=packet.GetSize()),
                  file=sys.stderr,
                  flush=True)
            if ns.core.Simulator.Now().GetSeconds() > 5:
                StreamingServer.LOGGING = False

    def receive(self):
        # 接收数据包和发送者的地址
        address = ns.network.Address()
        packet = self.m_socket.RecvFrom(address)
        if StreamingServer.LOGGING:
            inetAddress = ns.network.InetSocketAddress.ConvertFrom(address)
            print("在时间+{s}秒，服务器从{ip}端口{port}接收到了{b}字节"
                  .format(s=ns.core.Simulator.Now().GetSeconds(),
                          ip=inetAddress.GetIpv4(),
                          port=inetAddress.GetPort(),
                          b=packet.__deref__().GetSize()),
                  file=sys.stderr,
                  flush=True)
            if ns.core.Simulator.Now().GetSeconds() > 5:
                StreamingServer.LOGGING = False

        # 任何发送数据包到服务器的人将开始接收流
        # 1秒后开始流式传输块
        event = ns.pythonMakeEventSendBlock(
            self._send_block, self.m_socket, address)
        ns.core.Simulator.Schedule(ns.core.MilliSeconds(60), event)

    @staticmethod
    def _send_block(socket, address):
        # 静态函数，用于识别要发送数据包的StreamingServer实例并调用其发送方法
        instance = StreamingServer.socketToInstanceDict[socket]
        instance.send_block(address)

    @staticmethod
    def _send(socket, packet, address):
        # 静态函数，用于识别要发送数据包的StreamingServer实例并调用其发送方法
        instance = StreamingServer.socketToInstanceDict[socket]
        instance.send(packet, address)

    @staticmethod
    def _receive(socket):
        # 静态函数，用于识别要接收数据包的StreamingServer实例并调用其接收方法
        instance = StreamingServer.socketToInstanceDict[socket]
        instance.receive()


class StreamingClient(ns.applications.Application):
    LOGGING = True
    socketToInstanceDict = {}

    def __init__(self, node, server_address, port=StreamingServer.STREAMING_PORT, text_file=None):
        if not text_file:
            raise Exception("未指定文本文件")
        import os
        if not os.path.exists(text_file):
            raise Exception("文件不存在", text_file)
        super().__init__()  # 调用ns.Application的构造函数
        self.__python_owns__ = False  # 允许C++在Simulator::Destroy调用时销毁该对象
        self.port = port  # 服务器监听端口
        # 创建一个UDP套接字
        self.m_socket = ns.network.Socket.CreateSocket(
            node, ns.core.TypeId.LookupByName("ns3::UdpSocketFactory"))
        # 创建用于处理接收到的数据包的回调函数，使用StreamingClient类的静态函数
        # (这是为了让应用程序从Python中正常工作的一种解决方法)
        self.m_socket.SetRecvCallback(
            ns.make_rx_callback(StreamingClient._receive))
        # 将套接字注册为字典的键，并将其关联到该应用程序实例
        StreamingClient.socketToInstanceDict[self.m_socket] = self

        # 将数据包发送回发送者的Send函数安排在1秒后执行
        packet = ns.network.Packet(0)
        packet.__python_owns__ = False
        address = ns.network.InetSocketAddress(
            server_address, port).ConvertTo()
        event = ns.pythonMakeEventSend(
            StreamingClient._send, self.m_socket, packet, address)
        ns.core.Simulator.Schedule(ns.core.Seconds(1), event)

        self.output_text = open("text_out.txt", "w")

    def __del__(self):
        # 当对象销毁时，从字典中删除实例条目
        del StreamingClient.socketToInstanceDict[self.m_socket]
        self.output_text.close()

    def receive(self):
        # 接收数据包和发送者的地址
        address = ns.network.Address()
        packet = self.m_socket.RecvFrom(address)
        if StreamingClient.LOGGING:
            inetAddress = ns.network.InetSocketAddress.ConvertFrom(address)
            print("在时间+{s}秒，客户端从{ip}端口{port}接收到了{b}字节"
                  .format(s=ns.core.Simulator.Now().GetSeconds(),
                          ip=inetAddress.GetIpv4(),
                          port=inetAddress.GetPort(),
                          b=packet.__deref__().GetSize()),
                  file=sys.stderr,
                  flush=True)
            if ns.core.Simulator.Now().GetSeconds() > 5:
                StreamingClient.LOGGING = False

        # 从数据包中提取字节流并写入文件
        contents = packet.__deref__().ToString()
        self.output_text.write(contents)

    @staticmethod
    def _receive(socket):
        # 静态函数，用于识别要接收数据包的StreamingClient实例并调用其接收方法
        instance = StreamingClient.socketToInstanceDict[socket]
        instance.receive()

    def send(self, packet, address):
        # 将数据包发送到目标地址
        self.m_socket.SendTo(packet, 0, address)
        if StreamingClient.LOGGING:
            inetAddress = ns.network.InetSocketAddress.ConvertFrom(address)
            print("在时间+{s}秒，客户端从{ip}端口{port}发送了{b}字节"
                  .format(s=ns.core.Simulator.Now().GetSeconds(),
                          ip=inetAddress.GetIpv4(),
                          port=inetAddress.GetPort(),
                          b=packet.__deref__().GetSize()),
                  file=sys.stderr,
                  flush=True)
            if ns.core.Simulator.Now().GetSeconds() > 5:
                StreamingClient.LOGGING = False

    @staticmethod
    def _send(socket, packet, address):
        # 静态函数，用于识别要发送数据包的StreamingClient实例并调用其发送方法
        instance = StreamingClient.socketToInstanceDict[socket]
        instance.send(packet, address)


# 创建网络拓扑
nodes = ns.network.NodeContainer()
nodes.Create(2)

point_to_point = ns.point_to_point.PointToPointHelper()
devices = point_to_point.Install(nodes)

stack = ns.internet.InternetStackHelper()
stack.Install(nodes)

address = ns.internet.Ipv4AddressHelper()
address.SetBase(ns.network.Ipv4Address("10.1.1.0"),
                ns.network.Ipv4Mask("255.255.255.0"))
interfaces = address.Assign(devices)

# 创建文本服务器和客户端
server = StreamingServer(nodes.Get(0), text_file="text.txt")
client = StreamingClient(nodes.Get(1), server_address=interfaces.GetAddress(0))

# 启动文本服务器和客户端
server.send_block(interfaces.GetAddress(0))
client.receive()

# 运行仿真
ns.core.Simulator.Run()
ns.core.Simulator.Destroy()
