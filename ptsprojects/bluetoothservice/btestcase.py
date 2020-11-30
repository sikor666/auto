"""Test case that manages bluetooth service IUT"""

from ptsprojects.testcase import TestCaseLT1

class BTestCase(TestCaseLT1):
    """Bluetooth service test case class"""

    def __init__(self, *args, **kwargs):
        """Refer to TestCase.__init__ for parameters and their documentation"""

        super(BTestCase, self).__init__(*args, ptsproject_name="bluetoothservice", **kwargs)
