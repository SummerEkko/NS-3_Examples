from IPython.display import Video
from IPython.core.display import display

video_file = "./path/to/video.mp4"
display(Video(video_file, embed=False, autoplay=False))

def run_application(lossModel=False, byteErrorRate=0):
    # 创建节点容器
    nodes = ns.network.NodeContainer()
    nodes.Create(2)

    # 创建点对点通信助手
    pointToPoint = ns.point_to_point.PointToPointHelper()
    pointToPoint.SetDeviceAttribute("DataRate", ns.core.StringValue("5Mbps"))
    pointToPoint.SetChannelAttribute("Delay", ns.core.StringValue("2ms"))

    # 在节点上安装点对点设备
    devices = pointToPoint.Install(nodes)
    # devices 表示通过点对点通道连接的网络接口

    if lossModel:
        # 如果启用了丢包模型，向设备添加错误模型
        for i in range(devices.GetN()):
            # 创建速率错误模型
            em = ns.CreateObject("RateErrorModel")
            em.__deref__().SetAttribute("ErrorRate", ns.DoubleValue(byteErrorRate))
            # 设置错误率
            devices.Get(i).__deref__().SetAttribute("ReceiveErrorModel", ns.PointerValue(em))
            # 将错误模型附加到接收端的设备上

    # 在节点上安装互联网协议栈
    stack = ns.internet.InternetStackHelper()
    stack.Install(nodes)
    # 这将为基于 IP 的通信配置必要的协议和设置

    # 为设备/接口分配 IP 地址
    address = ns.internet.Ipv4AddressHelper()
    address.SetBase(ns.network.Ipv4Address("10.1.1.0"),
                    ns.network.Ipv4Mask("255.255.255.0"))
    interfaces = address.Assign(devices)
    # 每个设备都被分配一个指定范围内的 IP 地址

    # 创建和配置视频流服务器
    streamServer = StreamingServer(nodes.Get(1), video_file="video.mp4")
    nodes.Get(1).AddApplication(streamServer)
    serverApps = ns.ApplicationContainer()
    serverApps.Add(streamServer)
    serverApps.Start(ns.core.Seconds(1.0))
    serverApps.Stop(ns.core.Seconds(10.0))
    # 在仿真中启动和停止服务器应用程序

    # 获取服务器接口的地址
    address = interfaces.GetAddress(1)

    # 创建和配置视频流客户端
    streamClient = StreamingClient(nodes.Get(0), address, StreamingServer.STREAMING_PORT, video_file="video.mp4")
    clientApps = ns.ApplicationContainer()
    clientApps.Add(streamClient)
    clientApps.Start(ns.core.Seconds(2.0))
    clientApps.Stop(ns.core.Seconds(10.0))
    # 在仿真中启动和停止客户端应用程序

    # 运行仿真
    ns.Simulator.Run()
    ns.Simulator.Destroy()

    # 显示修改后的视频
    display(Video("video_out.mp4", embed=True, autoplay=False))

    # 重置日志记录状态
    StreamingServer.LOGGING = True
    StreamingClient.LOGGING = True

# 运行应用程序
run_application()
