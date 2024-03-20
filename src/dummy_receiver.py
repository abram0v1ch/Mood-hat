import argparse
from pythonosc import dispatcher, osc_server

def print_data(*args):
    data = args[3:]
    print(data)

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--ip', type=str, required=False,
                    default="127.0.0.1", help="The ip to listen on")
parser.add_argument('-p', '--udp_port', type=int, required=False, default=14739,
                    help="The UDP port to listen on")
parser.add_argument('-t', '--topic', type=str, required=False,
                    default='/random', help="The topic to print") # get random data
args = parser.parse_args()

dispatcher = dispatcher.Dispatcher()
dispatcher.map(args.topic, print_data)

server = osc_server.ThreadingOSCUDPServer(
    (args.ip, args.udp_port),
    dispatcher
)
print("Serving on {}".format(server.server_address))
server.serve_forever()
