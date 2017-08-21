from PyQt4 import *
from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtCore import *
from BalloonUpdate import *
from datetime import datetime
from time import sleep
import MySQLdb
import serial
import kiss
import aprs
import aprslib
import threading
import json
import time as t

try:
    # For Python 3.0 and later
    from urllib.request import urlopen
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen


class GetIridium(QtCore.QObject):

    # Received Signals
    start = pyqtSignal()
    setInterrupt = pyqtSignal()

    def __init__(self, MainWindow, host, user, password, name, IMEI):
        super(GetIridium, self).__init__()
        self.mainWindow = MainWindow
        self.dbHost = host
        self.dbUser = user
        self.dbPass = password
        self.dbName = name
        self.IMEI = IMEI
        self.iridiumInterrupt = False
        self.lastUnixtime = t.time()

        # Emitted Signals
        #self.mainWindow.noIridium.connect(self.mainWindow.iridiumNoConnection)
        self.mainWindow.iridiumNewLocation.connect(
            self.mainWindow.updateBalloonLocation)

    def getApiData(self):
        url = "https://api.aprs.fi/api/get?name=KC9VPW-11&what=loc&apikey=102673.5Jc2H40kGPJem8J&format=json"
        try:
            # Timeout may be redundant, if port 80 is timing out, port 3306
            # will probably also
            response = urlopen(url, timeout=5)
            data = response.read().decode("utf-8")
            return json.loads(data)
        except:
            return {}

    def run(self):
        """ Gets tracking information from the Iridium satellite modem by taking the information from the web api OR the SQL database at Montana State University """
        # modified this to use the Web API - pol.llovet@montana.edu
        #     the modification is crude and should be refactored. :P

        self.iridiumInterrupt = False
        while(not self.iridiumInterrupt):
            t.sleep(10)
            # Fetch the data from the API
            get_data = self.getApiData()
            if get_data:
                try:
                    print (get_data)
                    aprsEntry = get_data['entries'][0]
                    # set the data from the API values
                    unixTime = float(aprsEntry['time'])
                    print (self.lastUnixtime)
                    print (unixTime)
                    if unixTime > self.lastUnixtime:
                        self.lastUnixtime = unixTime
                        print(get_data)
                        remoteTime = datetime.utcfromtimestamp(
                            unixTime).strftime('%H:%M:%S')
                        remoteSeconds = float(remoteTime.split(
                            ':')[0]) * 3600 + float(remoteTime.split(':')[1]) * 60 + float(remoteTime.split(':')[2])
                        remoteLat = float(aprsEntry['lat'])
                        remoteLon = float(aprsEntry['lng'])
                        remoteAlt = float(aprsEntry['altitude']) * 3.28084 #convert m to ft

                        print("lat: {0}, long: {1}, alt: {2}".format(remoteLat, remoteLon, remoteAlt))

                        ### Create a new location object ###
                        newLocation = BalloonUpdate(remoteTime, remoteSeconds, remoteLat, remoteLon, remoteAlt,
                                                    "Iridium", self.mainWindow.groundLat, self.mainWindow.groundLon, self.mainWindow.groundAlt)
                        # Notify the main GUI of the new location
                        self.mainWindow.iridiumNewLocation.emit(newLocation)
                except Exception as e:
                    print("Error creating a new balloon location object from Iridium Data")
                    print(e)

        self.iridiumInterrupt = False

    def interrupt(self):
        self.iridiumInterrupt = True


class GetAPRS(QtCore.QObject):

    # Received Signals
    start = pyqtSignal()
    setInterrupt = pyqtSignal()

    def __init__(self, MainWindow, APRS, callsign):
        super(GetAPRS, self).__init__()
        self.mainWindow = MainWindow
        self.aprsSer = APRS
        self.aprsInterrupt = False
        self.callsign = callsign

        # Emitted Signals
        self.mainWindow.aprsNewLocation.connect(
            self.mainWindow.updateBalloonLocation)

    def run(self):
        """ Gets tracking information from the APRS receiver """
        print("Starting GetAPRS.run() method....")
        # aprsSer = APRS.getDevice()
        self.aprsSer.start()
        self.aprsSer.read(callback=self.parseAprsString, readmode=True)

        while(not self.aprsInterrupt):
            continue

        ### Clean Up ###
        try:
            self.aprsSer.stop()         # Close the APRS Serial Port
        except:
            print("Error closing APRS serial port")

        self.aprsInterrupt = False

    def parseAprsString(self, frame):
        ### Read the APRS serial port, and parse the string appropriately ###
        # Format:
        # "Callsign">CQ,WIDE1-1,WIDE2-2:!"Lat"N/"Lon"EO000/000/A="Alt"RadBug,23C,982mb,001
        # TT4 Format:
        # KC9VPW>APTT4,WIDE2-1:/063329h4156.04N/08738.57W>349/002/TinyTrak4 Alpha/A=000646
        # ###
        print("Attempting to parse an APRS frame...")
        try:
            line = aprs.Frame(frame)
            print(line)
            aprsMessage = aprslib.parse(str(line))
            print(aprsMessage)
            if(aprsMessage['from'] == self.callsign):
                print(line)
                
                # Get the individual values from the newly created list ###
                time = datetime.utcfromtimestamp(
                    t.time()).strftime('%H:%M:%S')
                aprsSeconds = float(time.split(
                    ':')[0]) * 3600 + float(time.split(':')[1]) * 60 + float(time.split(':')[2])

                lat = float(aprsMessage['latitude'])
                lon = float(aprsMessage['longitude'])
                alt = float(aprsMessage['altitude']) * 3.28084 #convert m to ft

                print("lat: {0}, long: {1}, alt: {2}".format(lat, lon, alt))

                ### Create a new location object ###
                try:
                    newLocation = BalloonUpdate(
                        time, aprsSeconds, lat, lon, alt, "APRS", self.mainWindow.groundLat, self.mainWindow.groundLon, self.mainWindow.groundAlt)
                except:
                    print(
                        "Error creating a new balloon location object from APRS Data")

                try:
                    # Notify the main GUI of the new location
                    self.mainWindow.aprsNewLocation.emit(newLocation)
                except Exception, e:
                    print(str(e))
        except Exception, e:
            print("Error retrieving APRS Data", e)

    def interrupt(self):
        self.aprsInterrupt = True
