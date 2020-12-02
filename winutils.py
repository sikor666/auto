"""Windows utilities"""

import os
import sys
import ctypes


class AdminStateUnknownError(Exception):
    pass


def have_admin_rights():
    """"Check if the process has Administrator rights"""
    try:
        return os.getuid() == 0
    except AttributeError:
        pass

    try:
        return ctypes.windll.shell32.IsUserAnAdmin() == 1
    except AttributeError:
        raise AdminStateUnknownError


def exit_if_admin():
    """Exit program if running as Administrator"""
    if have_admin_rights():
        sys.exit("Administrator rights are not required to run this script!")


def main():
    """Main."""

    is_admin = have_admin_rights()

    if is_admin:
        print("Running as administrator")
    else:
        print("Not running as administrator")

    exit_if_admin()


if __name__ == "__main__":
    main()
