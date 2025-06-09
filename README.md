# Fronius Modbus Simultion 

This python script provides a simulation of Fronius Smart Meter, from polling values from a Shelly Device and outputting the on ModBus TCP server.  The registers conform to the Fronius Sunspec map.

To use configure the ip address in the "meters" array and the meter name in the "meterdict" array.

At the moment the code supports a PM1 and 3EM - to test the difference the ip address on line 117 needs to updated.  

Each meter will be on it's own IP address the is defined setup_meters on row 317.

Each meter starts on it's own thread.

** Todo
- Add start IP address into a constant or config file
- Add code to determine meter type rather hard code
