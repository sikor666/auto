# Linux

    python3 -m pip install --user -r autoptsclient_requirements.txt

# Windows

    python.exe -m pip install --user -r autoptsserver_requirements.txt

# Running in Client/Server Mode

The bluetooth auto PTS framework uses a client server architecture.
With this setup the PTS automation server runs on Windows and the client runs on GNU/Linux.

The bluetooth auto PTS server requires the MQTT message broker to be running to communicate
with the tester application installed on Maxwell/Fusion. The easiest way is to run it on Windows Subsystem for Linux (WSL) using a command:

    mosquitto

The command below starts tester on Maxwell/Fusion:

    ./tester --host=[IP address of the windows server with the PTS testing equipment (Dongle)]

The command below starts AutoPTS server on Windows:

    python.exe autoptsserver.py

# Testing bluetooth service on Maxwell/Fusion

**Example of running all PBAP test cases from remote Linux host**

**PTS Workspace on Windows: "C:\Users\bluetooth\Documents\Profile Tuning Suite\Maxwell\Maxwell.pqw6"**
**AutoPTS Server IP: 192.168.1.103**
**Local IP Address:  192.168.1.104**

./autoptsclient-maxwell.py "C:\Users\bluetooth\Documents\Profile Tuning Suite\Maxwell\Maxwell.pqw6" -i 192.168.1.103 -l 192.168.1.104 -c PBAP
