#!/usr/bin/env python3



"""Common code for the auto PTS clients"""

import os
import errno
import sys
import logging
import xmlrpc.client
import queue
import threading
from traceback import format_exception
from xmlrpc.server import SimpleXMLRPCServer
import time
import datetime
import argparse
from termcolor import colored

from ptsprojects.testcase import PTSCallback
import ptsprojects.ptstypes as ptstypes
from config import SERVER_PORT, CLIENT_PORT

import tempfile
import xml.etree.ElementTree as ET

log = logging.debug

RUNNING_TEST_CASE = {}


class ClientCallback(PTSCallback):
    def __init__(self):
        pass

    def log(self, log_type, logtype_string, log_time, log_message, test_case_name):
        """Implements:

        interface IPTSControlClientLogger : IUnknown {
            HRESULT _stdcall Log(
                            [in] _PTS_LOGTYPE logType,
                            [in] LPWSTR szLogType,
                            [in] LPWSTR szTime,
                            [in] LPWSTR pszMessage);
        };

        test_case_name - To be identified by client in case of multiple pts
                         usage.
        """

        logger = logging.getLogger("{}.{}".format(self.__class__.__name__,
                                                  self.log.__name__))
        log = logger.info

        log("%s %s %s %s %s" % (ptstypes.PTS_LOGTYPE_STRING[log_type],
                                logtype_string, log_time, test_case_name,
                                log_message))

        try:
            if test_case_name in RUNNING_TEST_CASE:
                RUNNING_TEST_CASE[test_case_name].log(log_type, logtype_string,
                                                      log_time, log_message)

        except Exception as e:
            logging.exception("Log caught exception")

            # exit does not work, cause app is blocked in PTS.RunTestCase?
            sys.exit("Exception in Log")


class CallbackThread(threading.Thread):
    """Thread for XML-RPC callback server

    To prevent SimpleXMLRPCServer blocking whole app it is started in a thread

    """

    def __init__(self, port):
        log("%s.%s port=%r", self.__class__.__name__, self.__init__.__name__, port)
        threading.Thread.__init__(self)
        self.callback = ClientCallback()
        self.port = port

    def run(self):
        """Starts the xmlrpc callback server"""
        log("%s.%s", self.__class__.__name__, self.run.__name__)

        log("Serving on port %s ...", self.port)

        server = SimpleXMLRPCServer(("", self.port), allow_none=True, logRequests=False)
        server.register_instance(self.callback)
        server.register_introspection_functions()
        server.serve_forever()


def get_my_ip_address():
    """Returns the IP address of the host"""
    if get_my_ip_address.cached_address:
        return get_my_ip_address.cached_address

    my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    my_socket.connect(('8.8.8.8', 0))  # udp connection to google public dns
    my_ip_address = my_socket.getsockname()[0]

    get_my_ip_address.cached_address = my_ip_address
    return my_ip_address


get_my_ip_address.cached_address = None


def init_logging():
    """Initialize logging"""
    script_name = os.path.basename(sys.argv[0])  # in case it is full path
    script_name_no_ext = os.path.splitext(script_name)[0]

    log_filename = "%s.log" % (script_name_no_ext,)
    format = ("%(asctime)s %(name)s %(levelname)s %(filename)-25s "
              "%(lineno)-5s %(funcName)-25s : %(message)s")

    logging.basicConfig(format=format,
                        filename=log_filename,
                        filemode='w',
                        level=logging.DEBUG)


def init_pts_thread_entry(proxy, local_address, local_port, workspace_path,
                          bd_addr, enable_max_logs):
    """PTS instance initialization thread function entry"""

    sys.stdout.flush()
    proxy.restart_pts()
    print("(%r) OK" % (id(proxy),))

    proxy.callback_thread = CallbackThread(local_port)
    proxy.callback_thread.start()

    proxy.set_call_timeout(6000)  # milliseconds

    log("Server methods: %s", proxy.system.listMethods())
    log("PTS Version: %s", proxy.get_version())

    # cache locally for quick access (avoid contacting server)
    proxy.q_bd_addr = proxy.bd_addr()
    log("PTS BD_ADDR: %s", proxy.q_bd_addr)

    client_ip_address = local_address
    if client_ip_address is None:
        client_ip_address = get_my_ip_address()

    log("Client IP Address: %s", client_ip_address)

    proxy.register_xmlrpc_ptscallback(client_ip_address, local_port)

    log("Opening workspace: %s", workspace_path)
    proxy.open_workspace(workspace_path)

    if bd_addr:
        projects = proxy.get_project_list()
        for project_name in projects:
            log("Set bd_addr PIXIT: %s for project: %s", bd_addr, project_name)
            proxy.update_pixit_param(project_name, "TSPX_bd_addr_iut", bd_addr)

    proxy.enable_maximum_logging(enable_max_logs)


def init_pts(args):
    """Initialization procedure for PTS instances"""

    proxy_list = []
    thread_list = []

    init_logging()

    local_port = CLIENT_PORT

    for server_addr, local_addr in zip(args.ip_addr, args.local_addr):
        proxy = xmlrpc.client.ServerProxy(
            "http://{}:{}/".format(server_addr, SERVER_PORT),
            allow_none=True,)

        print("(%r) Starting PTS %s ..." % (id(proxy), server_addr))

        thread = threading.Thread(target=init_pts_thread_entry,
                                  args=(proxy, local_addr, local_port,
                                        args.workspace, args.bd_addr, args.enable_max_logs))
        thread.start()

        local_port += 1

        proxy_list.append(proxy)
        thread_list.append(thread)

    for index, thread in enumerate(thread_list):
        thread.join(timeout=180.0)

        # check init completed
        if thread.isAlive():
            raise Exception("(%r) init failed" % (id(proxy_list[index]),))

    return proxy_list


def get_result_color(status):
    if status == "PASS":
        return "green"
    elif status == "FAIL":
       return "red"
    elif status == "INCONC":
        return "yellow"
    else:
        return "magenta"


class TestCaseRunStats(object):
    def __init__(self, projects, test_cases, retry_count):

        self.run_count_max = retry_count + 1  # Run test at least once
        self.run_count = 0  # Run count of current test case
        self.num_test_cases = len(test_cases)
        self.num_test_cases_width = len(str(self.num_test_cases))
        self.max_project_name = len(max(projects, key=len)) if projects else 0
        self.max_test_case_name = len(max(test_cases, key=len)) if test_cases else 0
        self.margin = 3
        self.index = 0

        self.xml_results = tempfile.NamedTemporaryFile(delete=False).name
        root = ET.Element("results")
        tree = ET.ElementTree(root)
        tree.write(self.xml_results)

    def update(self, test_case_name, duration, status):
        tree = ET.parse(self.xml_results)
        root = tree.getroot()

        elem = root.find("./test_case[@name='%s']" % test_case_name)
        if elem is None:
            elem = ET.SubElement(root, 'test_case')

            elem.attrib["project"] = test_case_name.split('/')[0]
            elem.attrib["name"] = test_case_name
            elem.attrib["duration"] = str(duration)
            elem.attrib["status"] = ""

            run_count = 0
        else:
            run_count = int(elem.attrib["run_count"])

        elem.attrib["status"] = status
        elem.attrib["run_count"] = str(run_count + 1)

        tree.write(self.xml_results)

    def get_results(self):
        tree = ET.parse(self.xml_results)
        root = tree.getroot()

        results = {}

        for tc_xml in root.findall("./test_case"):
            results[tc_xml.attrib["name"]] = \
                tc_xml.attrib["status"]

        return results

    def get_status_count(self):
        tree = ET.parse(self.xml_results)
        root = tree.getroot()

        status_dict = {}

        for test_case_xml in root.findall("./test_case"):
            if test_case_xml.attrib["status"] not in status_dict:
                status_dict[test_case_xml.attrib["status"]] = 0

            status_dict[test_case_xml.attrib["status"]] += 1

        return status_dict

    def print_summary(self):
        """Prints test case list status summary"""
        print("\nSummary:\n")

        status_str = "Status"
        status_str_len = len(status_str)
        count_str_len = len("Count")
        total_str_len = len("Total")
        num_test_cases_str = str(self.num_test_cases)
        num_test_cases_str_len = len(num_test_cases_str)
        status_count = self.get_status_count()

        status_just = max(status_str_len, total_str_len)
        count_just = max(count_str_len, num_test_cases_str_len)

        title_str = ''
        border = ''

        for status, count in list(status_count.items()):
            status_just = max(status_just, len(status))
            count_just = max(count_just, len(str(count)))

            status_just += self.margin
            title_str = status_str.ljust(status_just) + "Count".rjust(count_just)
            border = "=" * (status_just + count_just)

        print(title_str)
        print(border)

        # print each status and count
        for status in sorted(status_count.keys()):
            count = status_count[status]
            print(status.ljust(status_just) + str(count).rjust(count_just))

        # print total
        print(border)
        print("Total".ljust(status_just) + num_test_cases_str.rjust(count_just))


def run_test_case_wrapper(func):
    def wrapper(*args):
        test_case_name = args[3]
        stats = args[4]

        run_count_max = stats.run_count_max
        run_count = stats.run_count
        num_test_cases = stats.num_test_cases
        num_test_cases_width = stats.num_test_cases_width
        max_project_name = stats.max_project_name
        max_test_case_name = stats.max_test_case_name
        margin = stats.margin
        index = stats.index

        print((str(index + 1).rjust(num_test_cases_width) +
               "/" +
               str(num_test_cases).ljust(num_test_cases_width + margin) +
               test_case_name.split('/')[0].ljust(max_project_name + margin) +
               test_case_name.ljust(max_test_case_name + margin - 1)), end=' ')
        sys.stdout.flush()

        start_time = time.time()
        status = func(*args)
        end_time = time.time() - start_time

        stats.update(test_case_name, end_time, status)

        retries_max = run_count_max - 1
        if run_count:
            retries_msg = "#{}".format(run_count)
        else:
            retries_msg = ""

        end_time_str = str(round(datetime.timedelta(
            seconds=end_time).total_seconds(), 3))

        result = ("{}".format(status).ljust(16) +
                  end_time_str.rjust(len(end_time_str)) +
                retries_msg.rjust(len("#{}".format(retries_max)) + margin))

        if sys.stdout.isatty():
            output_color = get_result_color(status)
            print(colored(result, output_color))
        else:
            print(result)

        return status, end_time

    return wrapper


def get_error_code(exc):
    """Return string error code for argument exception"""
    error_code = None

    if isinstance(exc, xmlrpc.client.Fault):
        error_code = ptstypes.E_XML_RPC_ERROR

    elif error_code is None:
        error_code = ptstypes.E_FATAL_ERROR

    log("%s returning error code %r for exception %r",
        get_error_code.__name__, error_code, exc)

    return error_code


def run_test_case_thread_entry(pts, workspace_path, test_case):
    """Runs the test case specified by a TestCase instance"""
    log("Starting TestCase %s %s %s",
        run_test_case_thread_entry.__name__, test_case, workspace_path)

    error_code = None

    try:
        RUNNING_TEST_CASE[test_case.name] = test_case
        test_case.status = "RUNNING"
        test_case.state = "RUNNING"
        error_code = pts.run_test_case(workspace_path, test_case.project_name, test_case.name)

        log("After run_test_case error_code=%r status=%r", error_code, test_case.status)

    except Exception as error:
        logging.exception(error)
        error_code = get_error_code(error)

    except BaseException:
        traceback_list = format_exception(sys.exc_info())
        logging.exception("".join(traceback_list))
        error_code = get_error_code(None)

    finally:
        if error_code == ptstypes.E_XML_RPC_ERROR:
            pts.recover_pts(workspace_path)
        test_case.state = "FINISHING"
        del RUNNING_TEST_CASE[test_case.name]

    log("Done TestCase %s %s", run_test_case_thread_entry.__name__, test_case)


@run_test_case_wrapper
def run_test_case(ptses, workspace_path, test_case_instances, test_case_name,
                  stats, session_log_dir):

    def test_case_lookup_name(name):
        """Return test case class instance if found or None otherwise"""
        if test_case_instances is None:
            return None

        for tc in test_case_instances:
            if tc.name == name:
                return tc

        return None

    logger = logging.getLogger()

    format = ("%(asctime)s %(name)s %(levelname)s %(filename)-25s "
                "%(lineno)-5s %(funcName)-25s : %(message)s")
    formatter = logging.Formatter(format)

    # Lookup TestCase class instance
    test_case = test_case_lookup_name(test_case_name)
    if test_case is None:
        # FIXME
        return 'NOT_IMPLEMENTED'

    test_case.reset()
    test_case.initialize_logging(session_log_dir)
    file_handler = logging.FileHandler(test_case.log_filename)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if test_case.status != 'init':
        # FIXME
        return 'NOT_INITIALIZED'

    # If we want to run tests on multiple PTS instances
    # we can create multiple threads here and implement
    # multiple classes that inherit from the TestCase class
    run_test_case_thread_entry(ptses[0], workspace_path, test_case)

    logger.removeHandler(file_handler)

    return test_case.status


def run_test_cases(ptses, test_case_instances, args):
    """Runs a list of test cases"""

    def run_or_not(test_case_name):
        if args.excluded:
            for n in args.excluded:
                if test_case_name.startswith(n):
                    return False

        if args.test_cases:
            for n in args.test_cases:
                if test_case_name.startswith(n):
                    return True

            return False

        return True

    now = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    session_log_dir = 'logs/' + now
    try:
        os.makedirs(session_log_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    test_cases = []

    projects = ptses[0].get_project_list()

    for project in projects:
        _test_case_list = ptses[0].get_test_case_list(project)
        test_cases += [tc for tc in _test_case_list if run_or_not(tc)]

    # Statistics
    stats = TestCaseRunStats(projects, test_cases, args.retry)

    for test_case in test_cases:
        stats.run_count = 0

        while True:
            status, duration = run_test_case(ptses, args.workspace, test_case_instances,
                                             test_case, stats, session_log_dir)

            if status == 'PASS' or stats.run_count == args.retry:
                break

            stats.run_count += 1

        stats.index += 1

    stats.print_summary()

    return stats.get_status_count(), stats.get_results()


class CliParser(argparse.ArgumentParser):
    def __init__(self, description):
        argparse.ArgumentParser.__init__(self, description=description)

        self.add_argument("-i", "--ip_addr", nargs="+",
                          help="IP address of the PTS automation servers")

        self.add_argument("-l", "--local_addr", nargs="+", default=None,
                          help="Local IP address of PTS automation client")

        self.add_argument("workspace",
                          help="Path to PTS workspace file to use for "
                               "testing. It should have pqw6 extension. "
                               "The file should be located on the "
                               "machine, where automation server is running.")

        self.add_argument("-a", "--bd-addr",
                          help="Bluetooth device address of the IUT")

        self.add_argument("-d", "--debug-logs", dest="enable_max_logs",
                          action='store_true', default=False,
                          help="Enable the PTS maximum logging. Equivalent "
                               "to running test case in PTS GUI using "
                               "'Run (Debug Logs)'")

        self.add_argument("-c", "--test-cases", nargs='+', default=[],
                          help="Names of test cases to run. Groups of "
                               "test cases can be specified by profile names")

        self.add_argument("-e", "--excluded", nargs='+', default=[],
                          help="Names of test cases to exclude. Groups of "
                               "test cases can be specified by profile names")

        self.add_argument("-r", "--retry", type=int, default=0,
                          help="Repeat test if failed. Parameter specifies "
                               "maximum repeat count per test")
