"""PBAP test cases"""

from ptsprojects.bluetoothservice.btestcase import BTestCase


def set_pixits(pts):
    """Setup PBAP profile PIXITS for workspace. Those values are used for test
    case if not updated within test case.

    PIXITS always should be updated accordingly to project and newest version of
    PTS.

    pts -- Instance of PyPTS"""

    # Set PBAP common PIXIT values
    pts.set_pixit("PBAP", "TSPX_auth_password", "0000")
    pts.set_pixit("PBAP", "TSPX_auth_user_id", "PTS")
    pts.set_pixit("PBAP", "TSPX_security_enabled", "TRUE")
    pts.set_pixit("PBAP", "TSPX_bd_addr_iut", "589EC6082D87")
    pts.set_pixit("PBAP", "TSPX_pin_code", "0000")
    pts.set_pixit("PBAP", "TSPX_time_guard", "6000000")
    pts.set_pixit("PBAP", "TSPX_use_implicit_send", "TRUE")
    pts.set_pixit("PBAP", "TSPX_client_class_of_device", "100204")
    pts.set_pixit("PBAP", "TSPX_server_class_of_device", "100204")
    pts.set_pixit("PBAP", "TSPX_PSE_vCardSelector", "0000000000000001")
    pts.set_pixit("PBAP", "TSPX_delete_link_key", "FALSE")
    pts.set_pixit("PBAP", "TSPX_PBAP_rfcomm_channel", "1")
    pts.set_pixit("PBAP", "TSPX_telecom_folder_path", "telecom")
    pts.set_pixit("PBAP", "TSPX_secure_simple_pairing_pass_key_confirmation", "FALSE")
    pts.set_pixit("PBAP", "TSPX_SPP_rfcomm_channel", "03")
    pts.set_pixit("PBAP", "TSPX_l2cap_psm", "1005")
    pts.set_pixit("PBAP", "TSPX_rfcomm_channel", "2")
    pts.set_pixit("PBAP", "TSPX_no_confirmations", "FALSE")
    pts.set_pixit("PBAP", "TSPX_Automation", "FALSE")
    pts.set_pixit("PBAP", "TSPX_search_criteria", "PTS")
    pts.set_pixit("PBAP", "TSPX_PullVCardEntry_invalid_value", "F1984D696B612048C3A46B6B696E656E")


def test_cases(pts):
    """Returns a list of PBAP test cases pts -- Instance of PyPTS"""

    test_cases = [
        BTestCase("PBAP", "PBAP/PCE/PBD/BV-01-C"),
        BTestCase("PBAP", "PBAP/PCE/PBF/BV-02-I"),
        BTestCase("PBAP", "PBAP/PCE/PDF/BV-01-I"),
        BTestCase("PBAP", "PBAP/PCE/SSM/BV-01-C"),
        BTestCase("PBAP", "PBAP/PCE/SSM/BV-02-C"),
        BTestCase("PBAP", "PBAP/PCE/SSM/BV-06-C"),
    ]

    return test_cases


def main():
    """Main."""

    test_cases_ = test_cases("AB:CD:EF:12:34:56")

    for test_case in test_cases_:
        print()
        print(test_case)


if __name__ == "__main__":
    main()
