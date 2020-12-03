import os
import wmi
import sys
import logging
import xmlrpc.client
import xmlrpc.server
import winutils
import ptscontrol
import paho.mqtt.client as mqtt
from config import SERVER_PORT

log = logging.debug


class PyPTSWithXmlRpcCallback(ptscontrol.PyPTS):
    """A child class that adds support of xmlrpc PTS callbacks to PyPTS"""

    def __init__(self):
        """Constructor"""

        log("%s", self.__init__.__name__)

        self.mqtt_client = mqtt.Client('autoptsserver')
        self.mqtt_client.connect(MQTT_BROKER_IP)
        self.mqtt_client.loop_start() # start loop to process received messages
        self.mqtt_client.subscribe("test/user")

        ptscontrol.PyPTS.__init__(self, self.mqtt_client)

        # address of the auto-pts client that started it's own xmlrpc server to
        # receive callback messages
        self.client_address = None
        self.client_port = None
        self.client_xmlrpc_proxy = None

    def __del__(self):
        """"Destructor"""
        self.mqtt_client.disconnect()
        self.mqtt_client.loop_stop()

    def register_xmlrpc_ptscallback(self, client_address, client_port):
        """Registers client callback. xmlrpc proxy/client calls this method
        to register its callback

        client_address -- IP address
        client_port -- TCP port
        """

        log("%s %s %d", self.register_xmlrpc_ptscallback.__name__,
            client_address, client_port)

        self.client_address = client_address
        self.client_port = client_port

        self.client_xmlrpc_proxy = xmlrpc.client.ServerProxy(
            "http://{}:{}/".format(self.client_address, self.client_port),
            allow_none=True)

        log("Created XMR RPC auto-pts client proxy, provides methods: %s" %
            self.client_xmlrpc_proxy.system.listMethods())

        self.register_ptscallback(self.client_xmlrpc_proxy)

    def unregister_xmlrpc_ptscallback(self):
        """Unregisters the client callback"""

        log("%s", self.unregister_xmlrpc_ptscallback.__name__)

        self.unregister_ptscallback()

        self.client_address = None
        self.client_port = None
        self.client_xmlrpc_proxy = None


def main():
    """Main."""
    winutils.exit_if_admin()

    script_name = os.path.basename(sys.argv[0])  # in case it is full path
    script_name_no_ext = os.path.splitext(script_name)[0]

    log_filename = "%s.log" % (script_name_no_ext,)
    format = ("%(asctime)s %(name)s %(levelname)s : %(message)s")

    logging.basicConfig(format=format,
                        filename=log_filename,
                        filemode='w',
                        level=logging.DEBUG)

    c = wmi.WMI()
    for iface in c.Win32_NetworkAdapterConfiguration(IPEnabled=True):
        print("Local IP address: %s DNS %r" % (iface.IPAddress, iface.DNSDomain))

    print("Starting PTS ...")
    pts = PyPTSWithXmlRpcCallback()
    print("OK")

    print("Serving on port {} ...".format(SERVER_PORT))

    server = xmlrpc.server.SimpleXMLRPCServer(("", SERVER_PORT), allow_none=True)
    server.register_instance(pts)
    server.register_introspection_functions()
    server.serve_forever()


if __name__ == "__main__":
    main()
