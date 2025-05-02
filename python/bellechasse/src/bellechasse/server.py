# import mido
import time
from collections import deque

import argparse
import math

from pythonosc.dispatcher import Dispatcher
from pythonosc import osc_server


def run():
    # print(mido.get_output_names())
    # print(mido.get_input_names())

    # inport = mido.open_input('Launchkey Mini MK3 MIDI Port')
    # outport = mido.open_output('Launchkey Mini MK3 MIDI Port')

    # msglog = deque()
    # echo_delay = 2

    # while True:
    #     while inport.iter_pending():
    #         msg = inport.receive()
    #         if msg.type != "clock":
    #             print(msg)
    #             msglog.append({"msg": msg, "due": time.time() + echo_delay})
    #     while len(msglog) > 0 and msglog[0]["due"] <= time.time():
    #         outport.send(msglog.popleft()["msg"])

    # print(__name__)
    # parser = argparse.ArgumentParser()
    # parser.add_argument(
    #     "--ip", default="127.0.0.1", help="The ip of the OSC server"
    # )
    # parser.add_argument(
    #     "--port",
    #     type=int,
    #     default=5005,
    #     help="The port the OSC server is listening on",
    # )
    # args = parser.parse_args()

    # client = udp_client.SimpleUDPClient(args.ip, args.port)

    # for x in range(10):
    #     client.send_message("/filter", random.random())
    #     time.sleep(1)

    def print_volume_handler(unused_addr, args, volume):
        print("[{0}] ~ {1}".format(args[0], volume))

    def print_compute_handler(unused_addr, args, volume):
        try:
            print("[{0}] ~ {1}".format(args[0], args[1](volume)))
        except ValueError:
            pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="127.0.0.1", help="The ip to listen on")
    parser.add_argument("--port", type=int, default=5005, help="The port to listen on")
    args = parser.parse_args()

    dispatcher = Dispatcher()
    dispatcher.map("/filter", print)
    dispatcher.map("/volume", print_volume_handler, "Volume")
    dispatcher.map("/logvolume", print_compute_handler, "Log volume", math.log)

    server = osc_server.ThreadingOSCUDPServer((args.ip, args.port), dispatcher)
    print("Serving on {}".format(server.server_address))
    server.serve_forever()
