# Introduction

The Bluetooth Profile Tuning Suite (PTS) is a Bluetooth testing tool provided by Bluetooth SIG. The PTS is a Windows program that is normally used in manual mode via its GUI.

This is the Bluetooth PTS automation framework. Greatly inspired by https://github.com/intel/auto-pts and based on Bluetooth SIG examples and documentation. Script ```autoptsserver.py``` uses PTSControl COM API of PTS to automate testing.

# Linux Prerequisites

    python3 -m pip install --user -r autoptsclient_requirements.txt

# Windows Prerequisites

    python.exe -m pip install --user -r autoptsserver_requirements.txt

# Running in Client/Server Mode

The bluetooth auto PTS framework uses a client server architecture.
With this setup the PTS automation server runs on Windows and the client runs on GNU/Linux.

To be able to run PTS in automation mode, there should be no PTS instances running in the GUI mode. Hence, before running ```autoptsserver.py``` scripts close the PTS GUI.

The bluetooth auto PTS server requires the MQTT message broker to be running to communicate
with the tester application installed on Maxwell/Fusion. The easiest way is to run it on Windows Subsystem for Linux (WSL) using a command:

    mosquitto

The command below starts tester on Maxwell/Fusion:

    ./tester --host=[IP address of the host with MQTT message broker]

The command below starts auto PTS server on Windows:

    python.exe autoptsserver.py

**Testing bluetooth service on Maxwell from remote Linux host**

```bash
# PTS Workspace on Windows: "C:\Users\bluetooth\Documents\Profile Tuning Suite\Maxwell\Maxwell.pqw6"
# Auto PTS Server IP: 192.168.1.103
# Local IP Address:  192.168.1.104

# Show help message and exit
./autoptsclient-maxwell.py --help

# Run all PBAP test cases from remote Linux host.
./autoptsclient-maxwell.py "C:\Users\bluetooth\Documents\Profile Tuning Suite\Maxwell\Maxwell.pqw6" \
-i 192.168.1.103 -l 192.168.1.104 -c PBAP

# Run PBAP/PCE/SSM/BV-02-C test case from remote Linux host with enable the PTS maximum logging.
./autoptsclient-maxwell.py "C:\Users\bluetooth\Documents\Profile Tuning Suite\Maxwell\Maxwell.pqw6" \
-i 192.168.1.103 -l 192.168.1.104 -c PBAP/PCE/SSM/BV-02-C -d

# Run PBAP test cases from remote Linux host without excluded list
./autoptsclient-maxwell.py "C:\Users\bluetooth\Documents\Profile Tuning Suite\Maxwell\Maxwell.pqw6" \
-i 192.168.1.103 -l 192.168.1.104 -c PBAP -e PBAP/PCE/PBD/BV-01-C PBAP/PCE/PBF/BV-02-I
```
