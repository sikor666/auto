"""Python bindings for PTSControl introp objects

Cause of tight coupling with PTS, this module is Windows specific
"""

import os
import wmi
import sys
import time
import logging
import argparse
import shutil
import win32com.client
import win32com.server.connect
import win32com.server.util
import pythoncom
import ptsprojects.ptstypes as ptstypes
import ctypes
import json

log = logging.debug

logtype_whitelist = [ptstypes.PTS_LOGTYPE_START_TEST,
                     ptstypes.PTS_LOGTYPE_END_TEST,
                     ptstypes.PTS_LOGTYPE_ERROR,
                     ptstypes.PTS_LOGTYPE_FINAL_VERDICT]

PTS_WORKSPACE_FILE_EXT = ".pqw6"


class PTSLogger(win32com.server.connect.ConnectableServer):
    """PTS control client logger callback implementation"""
    _reg_desc_ = "AutoPTS Logger"
    _reg_clsid_ = "{50B17199-917A-427F-8567-4842CAD241A1}"
    _reg_progid_ = "autopts.PTSLogger"
    _public_methods_ = ['Log'] + win32com.server.connect.ConnectableServer._public_methods_

    def __init__(self):
        """"Constructor"""
        super(PTSLogger, self).__init__()

        self._callback = None
        self._maximum_logging = False
        self._test_case_name = None

    def set_callback(self, callback):
        """Set the callback"""
        self._callback = callback

    def unset_callback(self):
        """Unset the callback"""
        self._callback = None

    def enable_maximum_logging(self, enable):
        """Enable/disable maximum logging"""
        self._maximum_logging = enable

    def set_test_case_name(self, test_case_name):
        """Required to identify multiple instances on client side"""
        self._test_case_name = test_case_name

    def Log(self, log_type, logtype_string, log_time, log_message):
        """Implements:

        void Log(
                        [in] unsigned int logType,
                        [in] BSTR szLogType,
                        [in] BSTR szTime,
                        [in] BSTR pszMessage);
        };
        """

        logger = logging.getLogger(self.__class__.__name__)
        log = logger.info

        log("%d %s %s %s" % (log_type, logtype_string, log_time, log_message))

        try:
            if self._callback is not None:
                if self._maximum_logging or log_type in logtype_whitelist:
                    self._callback.log(log_type, logtype_string, log_time,
                                       log_message, self._test_case_name)
        except Exception as e:
            logging.exception(repr(e))
            sys.exit("Exception in Log")


class PTSSender(win32com.server.connect.ConnectableServer):
    """PTS control client implicit send callback implementation"""
    _reg_desc_ = "AutoPTS Sender"
    _reg_clsid_ = "{9F4517C9-559D-4655-9032-076A1E9B7654}"
    _reg_progid_ = "autopts.PTSSender"
    _public_methods_ = ['OnImplicitSend'] + win32com.server.connect.ConnectableServer._public_methods_

    def __init__(self, mqtt_client):
        """"Constructor"""
        super(PTSSender, self).__init__()

        self._callback = None
        self._mqtt_response = None
        self._mqtt_client = mqtt_client
        self._mqtt_client.on_message = self.on_implicit_send_response

    def set_callback(self, callback):
        """Sets the callback"""
        self._callback = callback

    def unset_callback(self):
        """Unsets the callback"""
        self._callback = None

    def on_implicit_send_response(self, client, userdata, message):
        """Called when MQTT message has been received"""
        message = str(message.payload.decode("utf-8"))
        log("MQTT response: %s" % message)
        # parse message:
        command = json.loads(message)
        # the result is a Python dictionary:
        status = command["parameters"]["status"]
        log("MQTT response status: %s" % status)
        self._mqtt_response = status

    def OnImplicitSend(self, project_name, wid, test_case, description, style):
        """Implements:

        VARIANT OnImplicitSend(
                        [in] BSTR pszProjectName,
                        [in] unsigned short wID,
                        [in] BSTR szTestCase,
                        [in] BSTR szDescription,
                        [in] unsigned long style);
        };
        """
        logger = logging.getLogger(self.__class__.__name__)
        log = logger.info
        timer = 0

        # Remove whitespaces from project and test case name
        project_name = project_name.replace(" ", "")
        test_case = test_case.replace(" ", "")

        log("*" * 20)
        log("BEGIN OnImplicitSend:")
        log("project_name: %s %s" % (project_name, type(project_name)))
        log("wid: %d %s" % (wid, type(wid)))
        log("test_case_name: %s %s" % (test_case, type(test_case)))
        log("description: %s %s" % (description, type(description)))
        log("style: %s 0x%x", ptstypes.MMI_STYLE_STRING[style], style)

        # a Python object (dict):
        command = {
            "command": "ImplicitSend",
            "parameters": {
                "projectName": project_name,
                "wid": wid,
                "testCase": test_case,
                "description": description,
                "style": style,
            },
            "response_required": "true"
        }

        # convert into JSON:
        message = json.dumps(command)

        # the result is a JSON string:
        log("MQTT request: %s" % message)

        self._mqtt_response = None
        self._mqtt_client.publish('user/test', message)

        try:
            log("Wait for MQTT response")

            while not self._mqtt_response:
                # XXX: Ask for response every second
                timer = timer + 1
                # XXX: Timeout 90 seconds
                if timer > 90:
                    self._mqtt_response = "Cancel"
                    break

                log("Rechecking MQTT response...")
                time.sleep(1)

            log("MQTT response returned after %d sec, respose: %r",
                timer, self._mqtt_response)

        except Exception as e:
            log("Caught exception")
            log(e)
            # exit does not work, cause app is blocked in PTS.RunTestCase?
            sys.exit("Exception in OnImplicitSend")

        if self._mqtt_response:
            is_present = 1
        else:
            is_present = 0

        # Stringify response
        self._mqtt_response = str(self._mqtt_response)
        rsp_len = str(len(self._mqtt_response))
        is_present = str(is_present)

        log("END OnImplicitSend:")
        log("*" * 20)

        return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR,
                                       [self._mqtt_response, rsp_len, is_present])


def parse_ptscontrol_error(err):
    try:
        _, source, description, _, _, hresult = err.excepinfo

        ptscontrol_e = ctypes.c_uint32(hresult).value
        ptscontrol_e_string = ptstypes.PTSCONTROL_E_STRING[ptscontrol_e]

        logging.exception(ptscontrol_e_string)

        return ptscontrol_e_string

    except Exception:
        raise Exception(err)


class PyPTS:
    """PTS control interface.

    Provides wrappers around Interop.PTSControl.PTSControlClass methods and
    some additional features.

    For detailed documentation see 'Extended Automatiing - Using PTSControl'
    document provided with PTS in file Extended_Automating.pdf

    """

    def __init__(self, mqtt_client):
        """Constructor"""
        log("%s", self.__init__.__name__)

        self._mqtt_client = mqtt_client
        self._init_attributes()

        # This is done to have valid _pts in case client does not restart_pts
        # and uses other methods. Normally though, the client should
        # restart_pts, see its docstring for the details
        #
        # Another reason: PTS starting from version 6.2 returns
        # PTSCONTROL_E_IMPLICIT_SEND_CALLBACK_ALREADY_REGISTERED 0x849C004 in
        # RegisterImplicitSendCallbackEx if PTS from previous autoptsserver is
        # used
        self.restart_pts()

    def _init_attributes(self):
        """Initializes class attributes"""
        log("%s", self._init_attributes.__name__)

        self._pts = None
        self._pts_proc = None

        self._pts_logger = None
        self._pts_sender = None
        self._com_logger = None
        self._com_sender = None

        # Cached frequently used PTS attributes: for optimisation reasons it is
        # avoided to contact PTS. These attributes should not change anyway.
        self.__bd_addr = None
        self._pts_projects = {}

    def recover_pts(self, workspace_path, pts_timeout):
        """Recovers PTS from errors occured during RunTestCase call.

        The errors include timeout set by SetPTSCallTimeout. The only way to
        correctly recover is to restore PTS settings.

        """

        log("%s timeout=%d %s", self.recover_pts.__name__, pts_timeout, workspace_path)

        self.open_workspace(workspace_path)
        self.set_call_timeout(pts_timeout)

    def restart_pts(self):
        """Restarts PTS

        This function will block for couple of seconds while PTS starts

        """

        log("%s", self.restart_pts.__name__)

        # Startup of ptscontrol doesn't have PTS pid yet set - no pts running
        if self._pts_proc:
            self.stop_pts()
        time.sleep(1)  # otherwise there are COM errors occasionally
        self.start_pts()

    def start_pts(self):
        """Starts PTS

        This function will block for couple of seconds while PTS starts"""

        log("%s", self.start_pts.__name__)

        # Get PTS process list before running new PTS daemon
        c = wmi.WMI()
        pts_ps_list_pre = []
        pts_ps_list_post = []

        for ps in c.Win32_Process(name="PTS.exe"):
            pts_ps_list_pre.append(ps)

        self._pts = win32com.client.Dispatch('ProfileTuningSuite_6.PTSControlServer')

        # Get PTS process list after running new PTS daemon to get PID of
        # new instance
        for ps in c.Win32_Process(name="PTS.exe"):
            pts_ps_list_post.append(ps)

        pts_ps_list = list(set(pts_ps_list_post) - set(pts_ps_list_pre))
        if not pts_ps_list:
            log("Error during pts startup!")
            return

        self._pts_proc = pts_ps_list[0]

        log("Started new PTS daemon with pid: %d" % self._pts_proc.ProcessId)

        self._pts_logger = PTSLogger()
        self._pts_sender = PTSSender(self._mqtt_client)

        # cached frequently used PTS attributes: due to optimisation reasons it
        # is avoided to contact PTS. These attributes should not change anyway.
        self.__bd_addr = None

        self._com_logger = win32com.client.dynamic.Dispatch(
            win32com.server.util.wrap(self._pts_logger))
        self._com_sender = win32com.client.dynamic.Dispatch(
            win32com.server.util.wrap(self._pts_sender))

        self._pts.SetControlClientLoggerCallback(self._com_logger)
        self._pts.RegisterImplicitSendCallbackEx(self._com_sender)

        log("PTS Version: %s", self.get_version())
        log("PTS Bluetooth Address: %s", self.get_bluetooth_address())
        log("PTS BD_ADDR: %s" % self.bd_addr())

    def stop_pts(self):
        """Stops PTS"""

        try:
            log("About to stop PTS with pid: %d", self._pts_proc.ProcessId)
            self._pts_proc.Terminate()
            self._pts_proc = None

        except Exception as error:
            logging.exception(repr(error))

        self._init_attributes()

    def create_workspace(self, bd_addr, pts_file_path, workspace_name,
                         workspace_path):
        """Creates a new workspace"""

        log("%s %s %s %s %s", self.create_workspace.__name__, bd_addr,
            pts_file_path, workspace_name, workspace_path)

        self._pts.CreateWorkspace(bd_addr, pts_file_path, workspace_name,
                                  workspace_path)

    def open_workspace(self, workspace_path):
        """Opens existing workspace"""

        log("%s %s", self.open_workspace.__name__, workspace_path)

        if not os.path.isfile(workspace_path):
            raise Exception("Workspace file '%s' does not exist" %
                            (workspace_path,))

        specified_ext = os.path.splitext(workspace_path)[1]
        if PTS_WORKSPACE_FILE_EXT != specified_ext:
            raise Exception(
                "Workspace file '%s' extension is wrong, should be %s" %
                (workspace_path, PTS_WORKSPACE_FILE_EXT))

        log("Open workspace: %s", workspace_path)

        self._pts.OpenWorkspace(workspace_path)
        self._cache_test_cases()

    def _cache_test_cases(self):
        """Cache test cases"""
        self._pts_projects.clear()

        for i in range(0, self._pts.GetProjectCount()):
            project_name = self._pts.GetProjectName(i)
            self._pts_projects[project_name] = {}

            for j in range(0, self._pts.GetTestCaseCount(project_name)):
                test_case_name = self._pts.GetTestCaseName(project_name,
                                                           j)
                self._pts_projects[project_name][test_case_name] = j

    def get_project_list(self):
        """Returns list of projects available in the current workspace"""

        return tuple(self._pts_projects.keys())

    def get_project_version(self, project_name):
        """Returns project version"""

        return self._pts.GetProjectVersion(project_name)

    def get_test_case_list(self, project_name):
        """Returns list of active test cases of the specified project"""

        test_case_list = []

        for test_case_name in list(self._pts_projects[project_name].keys()):
            if self._pts.IsActiveTestCase(project_name, test_case_name):
                test_case_list.append(test_case_name)

        return tuple(test_case_list)

    def get_test_case_description(self, project_name, test_case_name):
        """Returns description of the specified test case"""

        test_case_index = self._pts_projects[project_name][test_case_name]

        return self._pts.GetTestCaseDescription(project_name, test_case_index)

    def run_test_case(self, workspace_path, pts_timeout, project_name, test_case_name):
        """Executes the specified Test Case.

        If an error occurs when running test case returns code of an error as a
        string, otherwise returns an empty string
        """

        log("Starting %s %s %s %s", self.run_test_case.__name__, project_name,
            test_case_name, workspace_path)

        self._pts_logger.set_test_case_name(test_case_name)

        error_code = None

        try:
            self._pts.RunTestCase(project_name, test_case_name)

        except pythoncom.com_error as e:
            error_code = parse_ptscontrol_error(e)

        if error_code is not None:
            self.stop_test_case(project_name, test_case_name)
            self.recover_pts(workspace_path, pts_timeout)

        log("Done %s %s %s out: %s", self.run_test_case.__name__,
            project_name, test_case_name, error_code)

        return error_code

    def stop_test_case(self, project_name, test_case_name):
        """Submits a request to stop the executing Test Case"""

        log("%s %s %s", self.stop_test_case.__name__, project_name,
            test_case_name)

        try:
            self._pts.StopTestCase()

        except pythoncom.com_error as e:
            parse_ptscontrol_error(e)

    def get_test_case_count_from_tss_file(self, project_name):
        """Returns the number of test cases that are available in the specified
        project according to TSS file."""

        return self._pts.GetTestCaseCountFromTSSFile(project_name)

    def get_test_cases_from_tss_file(self, project_name):
        """Returns array of test case names according to TSS file."""

        return self._pts.GetTestCasesFromTSSFile(project_name)

    def set_pics(self, project_name, entry_name, bool_value):
        """Set PICS

        Method used to setup workspace default PICS

        This wrapper handles exceptions that PTS throws if PICS entry is
        already set to the same value.

        PTS throws exception if the value passed to UpdatePics is the same as
        the value when PTS was started.

        In C++ HRESULT error with this value is returned:
        PTSCONTROL_E_PICS_ENTRY_NOT_CHANGED (0x849C0032)

        """
        log("%s %s %s %s", self.set_pics.__name__, project_name,
            entry_name, bool_value)

        try:
            self._pts.UpdatePics(project_name, entry_name, bool_value)

        except pythoncom.com_error as e:
            parse_ptscontrol_error(e)

    def set_pixit(self, project_name, param_name, param_value):
        """Set PIXIT

        Method used to setup workspace default PIXIT

        This wrapper handles exceptions that PTS throws if PIXIT param is
        already set to the same value.

        PTS throws exception if the value passed to UpdatePixitParam is the
        same as the value when PTS was started.

        In C++ HRESULT error with this value is returned:
        PTSCONTROL_E_PIXIT_PARAM_NOT_CHANGED (0x849C0021)

        """
        log("%s %s %s %s", self.set_pixit.__name__, project_name,
            param_name, param_value)

        try:
            self._pts.UpdatePixitParam(project_name, param_name, param_value)

        except pythoncom.com_error as e:
            parse_ptscontrol_error(e)

    def update_pixit_param(self, project_name, param_name, new_param_value):
        """Updates PIXIT

        This wrapper handles exceptions that PTS throws if PIXIT param is
        already set to the same value.

        PTS throws exception if the value passed to UpdatePixitParam is the
        same as the value when PTS was started.

        In C++ HRESULT error with this value is returned:
        PTSCONTROL_E_PIXIT_PARAM_NOT_CHANGED (0x849C0021)

        """
        log("%s %s %s %s", self.update_pixit_param.__name__, project_name,
            param_name, new_param_value)

        try:
            self._pts.UpdatePixitParam(project_name, param_name, new_param_value)

        except pythoncom.com_error as e:
            parse_ptscontrol_error(e)

    def enable_maximum_logging(self, enable):
        """Enables/disables the maximum logging."""

        log("%s %s", self.enable_maximum_logging.__name__, enable)
        self._pts.EnableMaximumLogging(enable)
        self._pts_logger.enable_maximum_logging(enable)

    def set_call_timeout(self, timeout):
        """Sets a timeout period in milliseconds for the RunTestCase() calls
        to PTS."""

        # timeout 0 = no timeout
        self._pts.SetPTSCallTimeout(timeout)

    def save_test_history_log(self, save):
        """This function enables automation clients to specify whether test
        logs have to be saved in the corresponding workspace folder.

        save -- Boolean

        """

        log("%s %s", self.save_test_history_log.__name__, save)
        self._pts.SaveTestHistoryLog(save)

    def get_bluetooth_address(self):
        """Returns PTS bluetooth address string"""

        return self._pts.GetPTSBluetoothAddress()

    def bd_addr(self):
        """Returns PTS Bluetooth address as a colon separated string"""
        # use cached address if available
        if not self.__bd_addr:
            a = self.get_bluetooth_address().upper()
            self.__bd_addr = ":".join(a[i:i + 2] for i in range(0, len(a), 2))

        return self.__bd_addr

    def get_version(self):
        """Returns PTS version"""

        return self._pts.GetPTSVersion()

    def register_ptscallback(self, callback):
        """Registers testcase.PTSCallback instance to be used as PTS log and
        implicit send callback"""

        log("%s %s", self.register_ptscallback.__name__, callback)

        self._pts_logger.set_callback(callback)
        self._pts_sender.set_callback(callback)

    def unregister_ptscallback(self):
        """Unregisters the testcase.PTSCallback callback"""

        log("%s", self.unregister_ptscallback.__name__)

        self._pts_logger.unset_callback()
        self._pts_sender.unset_callback()


def parse_args():
    """Parses command line arguments and options"""

    arg_parser = argparse.ArgumentParser(
        description="PTS Control")

    arg_parser.add_argument(
        "workspace",
        help="Path to PTS workspace to use for testing. It should have %s "
        "extension" % (PTS_WORKSPACE_FILE_EXT,))

    args = arg_parser.parse_args()

    return args


def main():
    """Rudimentary testing."""

    args = parse_args()

    script_name = os.path.basename(sys.argv[0])  # in case it is full path
    script_name_no_ext = os.path.splitext(script_name)[0]

    log_filename = "%s.log" % (script_name_no_ext,)
    logging.basicConfig(format='%(name)s [%(asctime)s] %(message)s',
                        filename=log_filename,
                        filemode='w',
                        level=logging.DEBUG)

    pts = PyPTS()

    pts.open_workspace(args.workspace)

    project_count = pts.get_project_count()
    print("Project count:", project_count)

    # print all projects and their test cases
    for project_index in range(project_count):
        project_name = pts.get_project_name(project_index)
        print("\nProject name:", project_name)
        print("Project version:", pts.get_project_version(project_name))
        test_case_count = pts.get_test_case_count(project_name)
        print("Test case count:", test_case_count)

        for test_case_index in range(test_case_count):
            test_case_name = pts.get_test_case_name(
                project_name, test_case_index)
            print("\nTest case project:", project_name)
            print("Test case name:", test_case_name)
            print("Test case description:", pts.get_test_case_description(
                project_name, test_case_index))
            # print("Is active test case:", pts.is_active_test_case(
            #     project_name, test_case_name))

    print("\n\n\n\nTSS file info:")

    # print all projects and their test cases
    for project_index in range(project_count):
        project_name = pts.get_project_name(project_index)
        print("\nProject name:", project_name)
        print("Project version:", pts.get_project_version(project_name))
        test_case_count = pts.get_test_case_count_from_tss_file(project_name)
        print("Test case count:", test_case_count)

        test_cases = pts.get_test_cases_from_tss_file(project_name)
        print(test_cases)

        for test_case in test_cases:
            print(test_case)

    pts.enable_maximum_logging(True)
    pts.enable_maximum_logging(False)

    pts.set_call_timeout(PTS_TIMEOUT)
    pts.set_call_timeout(0)

    pts.save_test_history_log(True)
    pts.save_test_history_log(False)

    print("PTS Bluetooth Address: ", pts.get_bluetooth_address())
    print("PTS BD_ADDR: ", pts.bd_addr())
    print("PTS Version: ", pts.get_version())


if __name__ == "__main__":
    main()
