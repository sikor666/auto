"""PTS test case python implementation"""

import os
import logging
import datetime
import errno
from . import ptstypes

log = logging.debug


class AbstractMethodException(Exception):
    """Exception raised if an abstract method is called."""
    pass


class PTSCallback(object):
    """Base class for PTS callback implementors"""

    def __init__(self):
        pass

    def log(self, log_type, logtype_string, log_time, log_message):
        """Implements:

        interface IPTSControlClientLogger : IUnknown {
            HRESULT _stdcall Log(
                            [in] _PTS_LOGTYPE logType,
                            [in] LPWSTR szLogType,
                            [in] LPWSTR szTime,
                            [in] LPWSTR pszMessage);
        };
        """
        raise AbstractMethodException()


class TestCase(PTSCallback):
    """A PTS test case"""

    def copy(self):
        """Copy constructor"""
        return TestCase(self.project_name, self.name, self.ptsproject_name,
                        self.log_filename, self.log_dir)

    def __init__(self, project_name, test_case_name,
                 ptsproject_name=None, log_filename=None, log_dir=None):
        """TestCase constructor"""

        self.project_name = project_name
        self.name = test_case_name
        # a.k.a. final verdict
        self.status = "init"
        self.state = None

        self.ptsproject_name = ptsproject_name
        self.log_filename = log_filename
        self.log_dir = log_dir

    def reset(self):
        self.status = "init"
        self.state = None

    def __str__(self):
        """Returns string representation"""
        return "%s %s" % (self.project_name, self.name)

    def initialize_logging(self, session_logging_dir):
        now = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        normalized_name = self.name.replace('/', '_')
        timestamp_name = "%s_%s" % (normalized_name, now)
        test_log_dir = os.path.join(session_logging_dir, timestamp_name)
        try:
            os.makedirs(test_log_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        log("Created logs directory %r", test_log_dir)

        self.log_dir = test_log_dir
        self.log_filename = os.path.join(test_log_dir, timestamp_name + ".log")

    def log(self, log_type, logtype_string, log_time, log_message):
        """Overrides PTSCallback method. Handles PTSControl.IPTSControlClientLogger.Log"""

        new_status = None

        # mark test case as started
        if log_type == ptstypes.PTS_LOGTYPE_START_TEST:
            new_status = "Started"

        # mark the final verdict of the test case
        # check for "final verdict" to avoid "Encrypted Verdict"
        # it could be 'Final verdict' or 'Final Verdict'
        elif log_type == ptstypes.PTS_LOGTYPE_FINAL_VERDICT and \
                logtype_string.lower() == "final verdict":

            if "PASS" in log_message:
                new_status = "PASS"
            elif "INCONC" in log_message:
                new_status = "INCONC"
            elif "FAIL" in log_message:
                new_status = "FAIL"
            else:
                new_status = "UNKNOWN VERDICT: %s" % log_message.strip()

        if new_status:
            self.status = new_status
            log("New status %s - %s", str(self), new_status)


class TestCaseLT1(TestCase):
    def copy(self):
        """Copy constructor"""

        test_case = super(TestCaseLT1, self).copy()
        test_case.name_lt2 = self.name_lt2

        return test_case

    def __init__(self, *args, **kwargs):
        name_lt2 = kwargs.pop('lt2', None)
        super(TestCaseLT1, self).__init__(*args, **kwargs)
        self.name_lt2 = name_lt2


class TestCaseLT2(TestCase):
    pass
