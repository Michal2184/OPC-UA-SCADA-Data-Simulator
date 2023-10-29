from time import sleep
from random import uniform
from opcua import ua, Server
import socket

# Main data set
liveData = {
    "Mixer": {
        'Temperature.PV': 71.816,
        'Level.PV': 0,
        'Pump1.PV': 10.00,
        'Pump1.CMD': 1,
        'Pump1.Speed.SP': 16.37,
        'Pump2.PV': 0,
        'Pump2.CMD': 0,
        'Pump2.Speed.SP': 11.24,
        'Inlet1.Position': 1,  # state open/closed
        'Inlet1.CMD': 1,  # turning on/off
        'Inlet2.Position': 0,
        'Inlet2.CMD': 0,
        'Inlet1.CLS': 0,
        'Inlet1.OLS': 1,
        'Inlet2.CLS': 1,
        'Inlet2.OLS': 0,
        'Outlet.CLS': 0,
        'Outlet.OLS': 0,
        'Agitator.Speed.PV': 3000,
        'Agitator.CMD': 0,
        'Agitator.PV': 0,
        'MixingTime.PV': 50,
        'Outlet.Position': 0,
        'Outlet.CMD': 0,
    }
}

#### used by simulator only
dataSet = liveData["Mixer"]
####


class Simulator:
    """" SIMULATOR ENGINE """
    def __init__(self):
        self.status = {
            'state': 1,
            'tempFlow': 1,
            'levelFlow': 1,
            'filling': 1,
            'draining': 0,
            'mixing': 0,
        }
        self.mixIter = 0

    def run(self):
        """ update values on every iteration """
        if self.status["filling"]:
            self.fillTank()

        if not self.status["filling"] and not self.status["draining"]:
            self.mixTank()

        if self.status["draining"]:
            self.drainTank()
            
        sleep(1)

    def fillTank(self):
        if 0 <= dataSet["Level.PV"] < 600 and dataSet["Inlet1.CMD"] and dataSet["Pump1.CMD"]:
            dataSet['Pump1.PV'] = dataSet["Pump1.Speed.SP"]
            dataSet["Level.PV"] += dataSet["Pump1.Speed.SP"]

        if dataSet["Level.PV"] > 600:
            dataSet["Inlet1.CMD"] = 0
            dataSet["Pump1.CMD"] = 0
            dataSet['Pump1.PV'] = 0
            dataSet["Inlet2.CMD"] = 1
            dataSet["Pump2.CMD"] = 1

        if 600 <= dataSet["Level.PV"] < 1000 and dataSet["Inlet2.CMD"] and dataSet["Pump2.CMD"]:
            dataSet['Pump2.PV'] = dataSet["Pump2.Speed.SP"]
            dataSet["Level.PV"] += dataSet["Pump2.Speed.SP"]
            if dataSet["Level.PV"] > 1000:
                dataSet["Level.PV"] = 1000

        if dataSet["Level.PV"] >= 1000:
            dataSet["Inlet2.CMD"] = 0
            dataSet["Agitator.CMD"] = 1
            dataSet["Pump2.CMD"] = 0
            dataSet['Pump2.PV'] = 0
            self.status["filling"] = 0
            self.status["mixing"] = 1

        if dataSet["Inlet1.CMD"] == 1:
            dataSet["Inlet1.Position"] = 1
            dataSet["Inlet1.OLS"] = 1
            dataSet["Inlet1.CLS"] = 0
        else: 
            dataSet["Inlet1.Position"] = 0
            dataSet["Inlet1.OLS"] = 0
            dataSet["Inlet1.CLS"] = 1

        if dataSet["Inlet2.CMD"] == 1:
            dataSet["Inlet2.Position"] = 1
            dataSet["Inlet2.OLS"] = 1
            dataSet["Inlet2.CLS"] = 0
        else:
            dataSet["Inlet2.Position"] = 0
            dataSet["Inlet2.OLS"] = 0
            dataSet["Inlet2.CLS"] = 1

    def mixTank(self):
        if self.status["mixing"] and dataSet["Agitator.CMD"]:
            dataSet['Agitator.PV'] = uniform(dataSet["Agitator.Speed.PV"] -100, dataSet["Agitator.Speed.PV"] + 100)
            if dataSet["Temperature.PV"] < 301:
                dataSet["Temperature.PV"] += 14.6
                if dataSet["Temperature.PV"] > 301:
                    dataSet["Temperature.PV"] = 300

        self.mixIter += 1
        if self.mixIter == dataSet['MixingTime.PV']:
            self.mixIter = 0
            self.status["mixing"] = 0
            dataSet["Agitator.CMD"] = 0
            dataSet["Agitator.PV"] = 0
            self.status["draining"] = 1
            dataSet["Outlet.CMD"] = 1
            

    def drainTank(self):
        if dataSet["Level.PV"] > 0 and dataSet["Outlet.CMD"]:
            dataSet["Level.PV"] -= 23.06
            if dataSet["Level.PV"] < 0:
                dataSet["Level.PV"] = 0
            if dataSet["Temperature.PV"] > 71.816:
                dataSet["Temperature.PV"] -= 5.2
                if dataSet["Temperature.PV"] < 71.816:
                    dataSet["Temperature.PV"] = 71.816

        if dataSet["Level.PV"] == 0:
            dataSet["Outlet.CMD"] = 0
            self.status["draining"] = 0
            self.status["filling"] = 1
            dataSet["Inlet1.CMD"] = 1
            dataSet["Pump1.CMD"] = 1

        if dataSet["Outlet.CMD"] == 1:
            dataSet["Outlet.Position"] = 1
        else:
            dataSet["Outlet.Position"] = 0



class OPCUAServer:
    def __init__(self):
        self.server = Server()
        self.server.set_endpoint(f"opc.tcp://{socket.gethostname()}:4840/OPCUA-Server/")
        self.uri = "OPC UA Simulation Server"
        self.idx = self.server.register_namespace(self.uri)
        self.objects = self.server.get_objects_node()
        self.simulated_data_node = self.objects.add_object(self.idx, "Mixer-Groups")
        self.num_equipments = 4
        self.equipments = {}
        self.createTags()
        self.sim = Simulator()
        print("OPC UA Sim loaded to memory...OK")

    def start(self):
        try:
            print("OPC UA Sim running....")
            self.server.start()
            try:
                # Update with new LiveData updated by the Simulator
                while True:
                    try:
                        # refresh values using simulator
                        self.sim.run()
                        for equipment_name, tags in self.equipments.items():
                            data = liveData["Mixer"]
                            # print(data, end="\n")
                            # print(tags, end="\n")
                            for tag_name, value in data.items():
                                tags[tag_name].set_value(value)
                                # print(tags[tag_name], value)
                        sleep(1)
                    except KeyboardInterrupt:
                        print("\nOPC UA Simulator Exited ... OK\n")
                        break
            finally:
                # Close the server when exiting
                self.server.stop()

        except ValueError:
            print("Error: Wrong hostname - check OPC server address !")
            

    def createTags(self):
        for i in range(self.num_equipments):
            equipment_name = f"Mixer{(i + 1) * 100}"
            # create delay in staring here
            self.equipments[equipment_name] = self.create_equipment_node(self.simulated_data_node, equipment_name, self.idx)
        
    def create_equipment_node(self, parent_node, equipment_name, namespace_idx):
        # Create an object node for the equipment
        equipment_node = parent_node.add_object(namespace_idx, equipment_name)
        print(equipment_node)
        tags = {}
        # Add variables for each tag to the equipment node
        for tag_name in liveData["Mixer"].keys():
            tags[tag_name] = equipment_node.add_variable(namespace_idx, tag_name, 0)
        return tags
    

if __name__ == "__main__":
    x = OPCUAServer()
    x.start()