"""Test case that manages bluetooth service IUT"""

from ptsprojects.testcase import TestCaseLT1, TestCaseLT2

class BTestCase(TestCaseLT1):
    """Bluetooth service test case class"""

    def __init__(self, *args, **kwargs):
        """Refer to TestCase.__init__ for parameters and their documentation"""

        super(BTestCase, self).__init__(*args, ptsproject_name="bluetoothservice", **kwargs)


class BTestCaseSlave(TestCaseLT2):
    """Bluetooth service helper test case as a 2nd uint """

    def __init__(self, *args, **kwargs):
        """ Refer to TestCase.__init__ for parameters and their documentation"""

        super(BTestCaseSlave, self).__init__(*args, ptsproject_name="bluetoothservice", **kwargs)
