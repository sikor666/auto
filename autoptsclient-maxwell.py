#!/usr/bin/env python3

"""Maxwell auto PTS client"""

import os
import sys

import autoptsclient_common as autoptsclient
import ptsprojects.bluetoothservice as autoprojects


def parse_args():
    """Parses command line arguments and options"""

    arg_parser = autoptsclient.CliParser(description="PTS automation client")

    return arg_parser.parse_args()


def main():
    """Main."""
    if os.geteuid() == 0:  # root privileges are not needed
        sys.exit("Please do not run this program as root.")

    args = parse_args()

    ptses = autoptsclient.init_pts(args)

    autoprojects.pbap.set_pixits(ptses[0])

    # test_cases = autoprojects.gap.test_cases(ptses[0])
    # test_cases += autoprojects.sm.test_cases(ptses[0])
    # test_cases += autoprojects.pbap.test_cases(ptses[0])
    test_cases = autoprojects.pbap.test_cases(ptses[0])

    autoptsclient.run_test_cases(ptses, test_cases, args)

    print("\nBye!")
    sys.stdout.flush()

    for pts in ptses:
        pts.unregister_xmlrpc_ptscallback()

    # not the cleanest but the easiest way to exit the server thread
    os._exit(0)


if __name__ == "__main__":
    # os._exit: not the cleanest but the easiest way to exit the server thread
    try:
        main()

    except KeyboardInterrupt:  # Ctrl-C
        os._exit(14)

    # SystemExit is thrown in arg_parser.parse_args and in sys.exit
    except SystemExit:
        raise  # let the default handlers do the work

    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(16)
