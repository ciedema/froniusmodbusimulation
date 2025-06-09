
## Shelly 3em to  Fronius Modbus

import sys
sys

#pymodbus componets
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSparseDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.server import StartTcpServer
import threading
import struct
import time
import json
import getopt

import socket
import signal
import os
import urllib.request
import asyncio

##################################################################
# Timer Class -used to call the update meters function repeatedly
##################################################################
class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = threading.Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False







#Meter IP Addresses
meters = ["192.168.20.103","192.168.20.104","192.168.20.105","192.168.20.106","192.168.20.108"]
#Names of Meters
meterdict={"Stove":0,"Power 1":1,"Power 2":2,"Lights":3,"Power 3":4,"Living Room AC":5,"Mst Bed and Office AC":6,"Mid Bed and Kitchen AC":7,"Water Pump":8,"Stove LH":9,"Air Con LH":10,"Hot Water LH":11,"Hot Water":12}

contexts = []
servers =[]
modbus_port=502
corrfactor = 1
i_corrfactor = int(corrfactor)
consumption = "0"
totalexport = "0"
totalimport = "0"
rtime = 0

ti_int1 = "0"
ti_int2 = "0"
exp_int1 = "0"
exp_int2 = "0"
ep_int1 = "0"
ep_int2 = "0"

#Convert Float into Big Endian unit(16) values.  This code needs to be reworked into something better so it clear that their two words being returned 
def pack_float_32(value_to_pack):
    int1=0
    int2=0
    if value_to_pack!=0:
       total_hex = hex(struct.unpack('<I', struct.pack('<f', value_to_pack))[0])
       total_hex_part1 = str(total_hex)[2:6]
       total_hex_part2 = str(total_hex)[6:10]
       int1  = int(total_hex_part1, 16)
       int2  = int(total_hex_part2, 16)
    return int1,int2


#interate of over meters
def update_meters():
    global meterdict
    global ep_int1
    global ep_int2
    global exp_int1
    global exp_int2
    global ti_int1
    global ti_int2

    for ip in meters:
        meter_count=3
        if ip=="192.168.20.108":
            meter_count=1
        for emeter in range(meter_count):
            metersetup=""
            meterdata=""
            totalexport=0
            totalimport=0
            power=0
            voltage=0
            current=0
            #Need to rework below so that it can figure out what sort of Shelly Device
            if ip=="192.168.20.108":  #PM1
                try:  #Incase we are offline
                    with urllib.request.urlopen("http://"+ip+"/rpc/Switch.GetConfig?id="+str(emeter), timeout=2) as url:
                         metersetup=json.load(url)
                    with urllib.request.urlopen("http://"+ip+"/rpc/Switch.GetStatus?id="+str(emeter)) as url:
                         meterdata=json.load(url)
                except:
                    print("Timeout connecting to device:"+ip)
                else:
                    #print(ip+" "+ str(emeter)+" "+metersetup["name"]+":"+str(meterdata["apower"]))
                    totalimport = float(meterdata["aenergy"]["total"])
                    totalexport = 0
                    power = float(meterdata["apower"])*-1
                    voltage=float(meterdata["voltage"])
                    current=float(meterdata["current"])
            else:  #Otherwise Assume 3EM
                try:
                    with urllib.request.urlopen("http://"+ip+"/settings/emeter/"+str(emeter), timeout=2) as url:
                        metersetup=json.load(url)
                    with urllib.request.urlopen("http://"+ip+"/emeter/"+str(emeter)) as url:
                        meterdata=json.load(url)
                    #print(ip+" "+ str(emeter)+" "+metersetup["name"]+":"+str(meterdata["power"]))
                except:
                    print("Timeout connecting to device:"+ip)
                else:
                    totalimport = float(meterdata["total"])
                    totalexport = float(meterdata["total_returned"])
                    power = float(meterdata["power"])*-1
                    voltage=float(meterdata["voltage"])
                    current=float(meterdata["current"])
            #Pack readings into Big Endian Floats
            curr_int1,curr_int2=pack_float_32(current)
            volt_int1,volt_int2=pack_float_32(voltage)
            ep_int1,ep_int2 = pack_float_32(power)
            var_int1,var_int2=pack_float_32(power*-1)
            t1_int1,t1_int2=pack_float_32(totalimport)
            exp_int1,exp_int2=pack_float_32(totalexport)
            #Quit if meter offline - needs to be cleaner (yes - effectivly a goto)
            if metersetup=="":
                return
            #Find Meter Context
            meter=meterdict[metersetup["name"]]
            context = contexts[meter]

            #We are writing FC 3 from Address 40071
            register = 3
            slave_id = 0x02
            address = 0x9C87
            #Set up values to write - maybe should be updated to smaller chunks of data pairs 32704,0 equates to NaN
            values = [curr_int1, curr_int2, #Ampere - AC Total Current Value [A] 40072
                      curr_int1, curr_int2, #Ampere - AC Current Value L1 [A] 40074 
                      32704, 0,               #Ampere - AC Current Value L2 [A] 40076   
                      32704, 0,               #Ampere - AC Current Value L3 [A] 40078  
                      volt_int1, volt_int2, #Voltage - Average Phase to Neutral [V] 40080 
                      volt_int1, volt_int2, #Voltage - Phase L1 to Neutral [V] 40082 
                      32704, 0,           #Voltage - Phase L2 to Neutral [V] 40084 
                      32704, 0,           #Voltage - Phase L3 to Neutral [V] 40086 
                      32704, 0,           #Voltage - Average Phase to Phase [V] 40088 
                      32704, 0,           #Voltage - Phase L1 to L2 [V] 40090 
                      32704, 0,           #Voltage - Phase L2 to L3 [V] 40092 
                      32704, 0,           #Voltage - Phase L1 to L3 [V] 40094 
                      16968, 0,           #AC Frequency [Hz] 40096
                      ep_int1, ep_int2,   #AC Power value (Total) [W] 40098 
                      ep_int1, ep_int2,   #AC Power Value L1 [W] 40100 
                      32704, 0,           #AC Power Value L2 [W] 40102 
                      32704, 0,           #AC Power Value L3 [W] 40104
                      var_int1, var_int2, #AC Apparent Power [VA] 40106 - just using the inverse of W for the moment need to use PF corrected 
                      var_int1, var_int2, #AC Apparent Power L1 [VA] 40108 
                      32704, 0,           #AC Apparent Power L2 [VA] 40110 
                      32704, 0,           #AC Apparent Power L3 [VA] 40112 
                      0, 0,               #AC Reactive Power [VAr] 40114 - just defaulting to zero for now
                      0, 0,               #AC Reactive Power L1 [VAr] 40116 
                      32704, 0,           #AC Reactive Power L2 [VAr] 40118 
                      32704, 0,           #AC Reactive Power L3 [VAr] 40120 
                      0, 0,               #AC power factor total [cosphi] 40122 
                      0, 0,               #AC power factor L1 [cosphi] 40124 
                      32704, 0,           #AC power factor L2 [cosphi] 40126 
                      32704, 0,           #AC power factor L3 [cosphi] 40128 
                      exp_int1, exp_int2, #Total Watt Hours Exportet [Wh] 40130
                      32704, 0,           #Watt Hours Exported L1 [Wh] 40132 
                      32704, 0,           #Watt Hours Exported L2 [Wh] 40134
                      32704, 0,           #Watt Hours Exported L3 [Wh] 40136
                      ti_int1, ti_int2,   #Total Watt Hours Imported [Wh] 40138
                      32704, 0,           #Watt Hours Imported L1 [Wh] 40140
                      32704, 0,           #Watt Hours Imported L2 [Wh] 40142
                      32704, 0,           #Watt Hours Imported L3 [Wh] 40144
                      exp_int1, exp_int2, #Total VA hours Exported [VA] 40146
                      32704, 0,           #VA hours Exported L1 [VA] 40148
                      32704, 0,           #VA hours Exported L2 [VA] 40150
                      32704, 0,           #VA hours Exported L3 [VA] 41052
                      ti_int1, ti_int2,   #Total VA hours Imported [VA] 40154
                      32704, 0,           #VA hours Imported L1 [VA] 40156
                      32704, 0,           #VA hours Imported L2 [VA] 40158
                      32704, 0,           #VA hours Imported L3 [VA] 40160
                      32704, 0,           #Total VAr Q1 hours imported [VAr] 40162
                      32704, 0,           #VAr hours Q1 imported L1 [VAr] 40164
                      32704, 0,           #VAr hours Q1 imported L2 [VAr] 40166
                      32704, 0,           #VAr hours Q1 imported L3 [VAr] 40168
                      32704, 0,           #Total VAr Q2 hours [VAr] 40170
                      32704, 0,           #VAr hours Q2 imported L1 [VAr] 40172
                      32704, 0,           #VAr hours Q2 imported L2 [VAr] 40174
                      32704, 0,           #VAr hours Q2 imported L3 [VAr] 40176
                      32704, 0,           #Total VAr Q3 hours [VAr] 40178
                      32704, 0,           #VAr hours Q3 imported L1 [VAr] 40180
                      32704, 0,           #VAr hours Q3 imported L2 [VAr] 40182
                      32704, 0,           #VAr hours Q3 imported L3 [VAr] 40184
                      32704, 0,           #Total VAr Q4 hours [VAr] 40186
                      32704, 0,           #VAr hours Q4 imported L1 [VAr] 40188
                      32704, 0,           #VAr hours Q4 imported L2 [VAr] 40190
                      32704, 0            #VAr hours Q4 imported L3 [VAr] 40192
                     ]
            #Update Values to Meter
            contexts[meter][0].setValues(register, address, values)





def start_meter(emeter,address):

    print(address)
    global contexts
    StartTcpServer(
        context=contexts[emeter],
        address=address,
        framer='socket',
    )


def setup_meters ():
    global contexts
    global modbus_port
    global servers
    for emeter in range(13):
        metertype=213
        if emeter==12:
            metertype=213
        datablock = ModbusSparseDataBlock({

            40001: [21365, 28243],
            40003: [1],
            40004: [65],
            40005: [18034,28526,26997,29440,0,0,0,0,0,0,0,0,0,0,0,0],                       #Manufacturer "Fronius
            40021: [21357,24946,29728,19813,29797,29216,13875,16685,12544,0,0,0,0,0,0,0],   #Device Model "Smart Meter
            40037: [15472,29289,28001,29305,15872,0,0,0],                                   #Options N/A
            40045: [12590,14592,0,0,0,0,0,0],                                               #Software Version  N/A
            40053: [48,48,48,48,48,48,48,49,0,0,0,0,0,0,0,emeter],                          #Serial Number: 00000
            40069: [2],                                                                     #Modbus TCP Address:
            40070: [metertype],                                                             #Meter Type
            40071: [124],                                                                   #Modbus Length
            40072: [0,0,0,0],                                                               #Current
            40076: [32704,0,32704],
            40080: [0,0,0,0],                                                               #Voltage
            40084: [32704,0,32704,0,32704,0,32704,0,32704,0,32704,0],
            40096: [0,0],                                                                   #Frequency
            40098: [0,0,0,0],                                                               #Power
            40102: [32704,0,32704,0],
            40106: [0,0,0,0],                                                               #VA
            40110: [32704,0,32704,0],
            40114: [0,0,0,0],                                                               #VAR
            40118: [32704,0,32704,0],
            40122: [0,0,0,0],                                                               #PF
            40126: [32704,0,32704,0],
            40130: [0,0],                                                                   #Exported
            40132: [32704,0,32704,0,32704,0],
            40138: [0,0],                                                                   #Imported
            40140: [32704,0,32704,0,32704,0],
            40146: [0,0],                                                                   #Exported VA
            40148: [32704,0,32704,0,32704,0],
            40154: [0,0],                                                                   #Imported VA
            40156: [32704,0],
            40158: [32704,0,32704,0,32704,0,32704,0,32704,0,  #8
                    32704,0,32704,0,32704,0,32704,0,32704,0,  #9
                    32704,0,32704,0,32704,0,32704,0,32704,0,  #10
                    32704,0,32704,0,32704,0,32704,0,32704,0,  #11
                    32704,0,32704,0,32704,0,32704,0,32704,0,  #12
                    32704,0,32704,0],
            40194: [0, 0],                                                                   #Event
            40196: [65535, 0],                                                               #End Block
        })
        #Setup Slave Store
        slaveStore = ModbusSlaveContext(
            di=datablock,
            co=datablock,
            hr=datablock,
            ir=datablock,
        )
        #Add Store to Context - use Single True as it doesn't what the Slave ID is - Fronius doesn't support connecting to more slave on the same IP Address
        contexts.append(ModbusServerContext(slaves=slaveStore, single=True))

        #As Fronius doesn't support more than one Slave on the same IP address we need to start a server on each IP address. We are going to start meter on IPs 
        #starting at 192.168.20.230 - this needs to moved to constants or a config file.
        ip_last_octet=230+emeter
        ip_address="192.168.20."+str(ip_last_octet)
        address = (ip_address, modbus_port)
        #Start each on a new thread
        x=threading.Thread(target=start_meter,args=(emeter,address))
        x.start()

    ###############################################################
    # Run Update Register every 5 Seconds
    ###############################################################
    update_meters
    time = 20  # 5 seconds delay
    rt = RepeatedTimer(time, update_meters, )


if __name__ == "__main__":
    setup_meters()
