## Shelly 3em to  Fronius Modbus


from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSparseDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.transaction import ModbusSocketFramer, ModbusAsciiFramer
from pymodbus.server import StartTcpServer
from pymodbus.server import StartAsyncTcpServer
import threading
import struct
import time
import json
import getopt
import sys
import socket
import signal
import os
import urllib.request
import asyncio

###############################################################
# Timer Class
###############################################################
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








meters = ["192.168.20.103","192.168.20.104","192.168.20.105"]
meterdict={"Grid":0,"Hot Water":1,"Stove":2,"Power":3,"Living Room AC":4,"Master Bedroom and Office AC":5,"Water Pump":6,"Kitchen, MB AC":7,"Little House":8}

contexts = []
servers =[]
modbus_port=502
corrfactor = 1000
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





def update_meters():
    global meterdict
    global ep_int1
    global ep_int2
    global exp_int1
    global exp_int2
    global ti_int1
    global ti_int2

    for ip in meters:
        for emeter in range(3):
            with urllib.request.urlopen("http://"+ip+"/settings/emeter/"+str(emeter)) as url:
                metersetup=json.load(url)
            with urllib.request.urlopen("http://"+ip+"/emeter/"+str(emeter)) as url:
                meterdata=json.load(url)
            #print(ip+" "+ str(emeter)+" "+metersetup["name"]+":"+str(meterdata["power"]))
#            Considering correction factor
            #print("Corrected Values:"+metersetup["name"] )

            float_totalimport = float(meterdata["total"])
            totalimport_corr = float_totalimport*i_corrfactor
            #print (totalimport_corr)
            float_totalexport = float(meterdata["total_returned"])
            totalexport_corr = float_totalexport*i_corrfactor
            #print (totalexport_corr)

#            Converting current power consumption out of MQTT payload to Modbus register

            electrical_power_float = float(meterdata["power"]) #extract value out of payload
            #print (electrical_power_float)

            if electrical_power_float == 0:
                ep_int1 = 0
                ep_int2 = 0
            else:
                electrical_power_hex = hex(struct.unpack('<I', struct.pack('<f', electrical_power_float))[0])
                electrical_power_hex_part1 = str(electrical_power_hex)[2:6] #extract first register part (hex)
                electrical_power_hex_part2 = str(electrical_power_hex)[6:10] #extract seconds register part (hex)
                ep_int1 = int(electrical_power_hex_part1, 16) #convert hex to integer because pymodbus converts back to hex itself
                ep_int2 = int(electrical_power_hex_part2, 16) #convert hex to integer because pymodbus converts back to hex itself

#           Converting total import value of smart meter out of MQTT payload into Modbus register
            if float_totalimport ==0:
                t1_int1 = 0
                t1_int2 = 0
            else:
                total_import_float = int(totalimport_corr)
                total_import_hex = hex(struct.unpack('<I', struct.pack('<f', total_import_float))[0])
                total_import_hex_part1 = str(total_import_hex)[2:6]
                total_import_hex_part2 = str(total_import_hex)[6:10]
                ti_int1  = int(total_import_hex_part1, 16)
                ti_int2  = int(total_import_hex_part2, 16)

#           Converting total export value of smart meter out of MQTT payload into Modbus register
            if float_totalexport ==0:
                exp_int1 = 0
                exp_int2 = 0
            else:
                total_export_float = int(totalexport_corr)
                total_export_hex = hex(struct.unpack('<I', struct.pack('<f', total_export_float))[0])
                total_export_hex_part1 = str(total_export_hex)[2:6]
                total_export_hex_part2 = str(total_export_hex)[6:10]
                exp_int1 = int(total_export_hex_part1, 16)
                exp_int2 = int(total_export_hex_part2, 16)
            meter=meterdict[metersetup["name"]]
            #print ("Meter no "+str(contexts[meter]))
            context = contexts[meter]
            register = 3
            slave_id = 0x01
            address = 0x9C87
            values = [0, 0,               #Ampere - AC Total Current Value [A]
                      0, 0,               #Ampere - AC Current Value L1 [A]
                      0, 0,               #Ampere - AC Current Value L2 [A]
                      0, 0,               #Ampere - AC Current Value L3 [A]
                      0, 0,               #Voltage - Average Phase to Neutral [V]
                      0, 0,               #Voltage - Phase L1 to Neutral [V]
                      0, 0,               #Voltage - Phase L2 to Neutral [V]
                      0, 0,               #Voltage - Phase L3 to Neutral [V]
                      0, 0,               #Voltage - Average Phase to Phase [V]
                      0, 0,               #Voltage - Phase L1 to L2 [V]
                      0, 0,               #Voltage - Phase L2 to L3 [V]
                      0, 0,               #Voltage - Phase L1 to L3 [V]
                      0, 0,               #AC Frequency [Hz]
                      ep_int1, 0,         #AC Power value (Total) [W] ==> Second hex word not needed
                      0, 0,               #AC Power Value L1 [W]
                      0, 0,               #AC Power Value L2 [W]
                      0, 0,               #AC Power Value L3 [W]
                      0, 0,               #AC Apparent Power [VA]
                      0, 0,               #AC Apparent Power L1 [VA]
                      0, 0,               #AC Apparent Power L2 [VA]
                      0, 0,               #AC Apparent Power L3 [VA]
                      0, 0,               #AC Reactive Power [VAr]
                      0, 0,               #AC Reactive Power L1 [VAr]
                      0, 0,               #AC Reactive Power L2 [VAr]
                      0, 0,               #AC Reactive Power L3 [VAr]
                      0, 0,               #AC power factor total [cosphi]
                      0, 0,               #AC power factor L1 [cosphi]
                      0, 0,               #AC power factor L2 [cosphi]
                      0, 0,               #AC power factor L3 [cosphi]
                      exp_int1, exp_int2, #Total Watt Hours Exportet [Wh]
                      0, 0,               #Watt Hours Exported L1 [Wh]
                      0, 0,               #Watt Hours Exported L2 [Wh]
                      0, 0,               #Watt Hours Exported L3 [Wh]
                      ti_int1, ti_int2,   #Total Watt Hours Imported [Wh]
                      0, 0,               #Watt Hours Imported L1 [Wh]
                      0, 0,               #Watt Hours Imported L2 [Wh]
                      0, 0,               #Watt Hours Imported L3 [Wh]
                      0, 0,               #Total VA hours Exported [VA]
                      0, 0,               #VA hours Exported L1 [VA]
                      0, 0,               #VA hours Exported L2 [VA]
                      0, 0,               #VA hours Exported L3 [VA]
                      0, 0,               #Total VAr hours imported [VAr]
                      0, 0,               #VA hours imported L1 [VAr]
                      0, 0,               #VA hours imported L2 [VAr]
                      0, 0                #VA hours imported L3 [VAr]
]

            contexts[meter][0].setValues(register, address, values)





def start_meter(emeter,address):

    print(address)
    global contexts
    StartTcpServer(
        context=contexts[emeter],
        address=address,
        framer=ModbusSocketFramer,
    )

def setup_meters ():
    global contexts
    global modbus_port
    global servers
    for emeter in range(9):
        datablock = ModbusSparseDataBlock({

            40001:  [21365, 28243],
            40003:  [1],
            40004:  [65],
            40005:  [70,114,111,110,105,117,115,0,0,0,0,0,0,0,0,0,         #Manufacturer "Fronius
                    83,109,97,114,116,32,77,101,116,101,114,32,54,51,65,0, #Device Model "Smart Meter
                    0,0,0,0,0,0,0,0,                                       #Options N/A
                    0,0,0,0,0,0,0,0,                                       #Software Version  N/A
                    48,48,48,48,48,48,48,49,0,0,0,0,0,0,0,emeter,               #Serial Number: 00000
                    emeter+10],                                                  #Modbus TCP Address:
            40070: [213],
            40071: [124],
            40072: [0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0,0,0,0,0,0,0,
                    0,0,0,0],

            40196: [65535, 0],
        })
        slaveStore = ModbusSlaveContext(
            di=datablock,
            co=datablock,
            hr=datablock,
            ir=datablock,
        )
        contexts.append(ModbusServerContext(slaves=slaveStore, single=True))

        ###############################################################
        # Run Update Register every 5 Seconds
        ###############################################################
        time = 10  # 5 seconds delay
        rt = RepeatedTimer(time, update_meters, )


        ip_address="192.168.20.23"+str(emeter)
        #print("### start server, listening on "+ip_address+":"+str(modbus_port))
        address = (ip_address, modbus_port)
        #context=contexts[emeter]
        #print(address)
        x=threading.Thread(target=start_meter,args=(emeter,address))
        x.start()
#        servers.append(await StartAsyncTcpServer(
#            context=contexts[emeter],
#            address=address,
#            framer=ModbusSocketFramer,
#            allow_reuse_addyress=True,
#        ))




if __name__ == "__main__":
    setup_meters()
