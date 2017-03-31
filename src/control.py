from dronekit import connect as drone_connect
from dronekit import *
import exceptions
import tools
import config
import eventlet
from listeners import Listen

eventlet.monkey_patch()

class DroneControl(object):
    def __init__(self, local, sio, app=""):
        self.app = app
        self.sio = sio
        self.vehicle = []
        self.success = False
        self.cmds = ""
        self.connect(local=local)
        self.taking_off = False
        self.critical = False
        self.listener = None

    def connect(self, local):
        try:
            if local:
                self.vehicle = drone_connect("127.0.0.1:14550", wait_ready=True,
                                             heartbeat_timeout=config.DRONE_HEARTBEAT)
            else:
                self.vehicle = drone_connect(tools.port_return(), baud=57600, wait_ready=True,
                                             heartbeat_timeout=config.DRONE_HEARTBEAT)
            self.cmds = self.vehicle.commands
            self.success = True
            self.listener = Listen(self.vehicle)
            self.download_missions()
            self.clear_missions()

            print 'Drone connected'
            self.sio.emit('response', {'data': "Drone connected"})

        # Bad TTY connection
        except exceptions.OSError as e:
            print 'No serial exists!'
            self.sio.emit('response', {'data': 'No serial exists!'})

        # API Error
        except APIException:
            print 'Timeout!'
            self.sio.emit('response', {'data': 'Timeout!'})

        # Other error
        except:
            print 'Some other error!'
            self.sio.emit('response', {'data': 'Some other error!'})

    def disconnect(self):
        if self.success:
            self.listener._remove_listeners()
        if self.vehicle != []:
            self.success = False
            self.vehicle.close()
        else:
            print "Not connected!"
            self.sio.emit("response", {'data': "Not connected!"})


    def _test_mission(self):
        if not self.success:
            print "Drone connection unsuccessful"
            self.sio.emit('response', {'data': "Drone connection unsuccessful"})
            return []
        self.clear_missions()
        self.arm_and_takeoff(2)
        # self.mission_fly_to(-35.362753, 149.164526, 3)
        self.mission_change_alt(3)
        self.mission_RTL()
        self.mission_upload()
        self.vehicle_auto()

    def is_safe(self):
        return self.vehicle.armed and not self.critical

    def vehicle_auto(self):
        while self.vehicle.mode != VehicleMode("AUTO"):
            self.vehicle.mode = VehicleMode("AUTO")
            print "Changing mode to AUTO"
            self.sio.emit('response', {'data': "Changing mode to AUTO"})
            time.sleep(1)
        print "Switched to AUTO"
        self.sio.emit("response", {'data': "Switched to AUTO"})

    def vehicle_auto_safe(self):
        if config.AUTO_ON and self.vehicle.mode.name == "GUIDED" and self.is_safe():
            self.vehicle_auto()

    def download_missions(self):
        self.cmds.download()
        self.cmds.wait_ready()

    def clear_missions(self):
        self.cmds.clear()
        self.mission_upload()
        self.download_missions()

    def mission_upload(self):
        self.cmds.upload()

    def mission_fly_to(self, lat, lon, alt):
        if self.taking_off:
            return None
        cmd = Command(0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, lat, lon, alt)
        self.cmds.add(cmd)
        self.sio.emit('response', {'data': "Mission: Fly to: " + str(lat) + " " + str(lon) + " " + str(alt)})

    def mission_RTL(self):
        if self.taking_off:
            return None
        cmd = Command(0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        self.cmds.add(cmd)
        self.sio.emit('response', {'data': "Mission: Return To Launch"})

    def mission_land(self):
        if self.taking_off:
            return None
        cmd = Command(0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_LAND, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        self.cmds.add(cmd)
        self.sio.emit('response', {'data': "Mission: Land"})

    def mission_change_alt(self, alt):
        if self.taking_off:
            return None
        cmd = Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 0, alt)
        self.cmds.add(cmd)
        self.sio.emit('response', {'data': "Mission: Change altitude to: " + str(alt)})

    def mission_set_home(self, lat=0, lon=0, alt=0):
        # Should not be used as it causes errors and unexpected behaviour (Only fixed in AC 3.3)
        home = 2
        if lat == 0 and lon == 0 and alt == 0:
            home = 1
        cmd = Command(0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, home, 0, 0, 0, 0, 0, lat, lon, alt)
        self.cmds.add(cmd)

    def pre_arm_check(self):
        for fail in range(0, config.PRE_ARM_WAIT):
            if self.vehicle.is_armable:
                print "Pre arm check COMPLETE!"
                self.sio.emit('response', {'data': "Pre arm check COMPLETE!"})

                return True
            print "Waiting for vehicle to initialise..."
            self.sio.emit('response', {'data': "Waiting for vehicle to initialise..."})

            time.sleep(1)
        print "Failed pre arm check"
        self.sio.emit('response', {'data': "Failed pre arm check"})

        return False

    def vehicle_guided(self):
        while self.vehicle.mode.name != "GUIDED":
            self.vehicle.mode = VehicleMode("GUIDED")
            print "Changing mode to GUIDED"
            self.sio.emit('response', {'data': "Changing mode to GUIDED"})
            time.sleep(1)
        print "Switched to GUIDED"
        self.sio.emit("response", {'data': "Switched to GUIDED"})

    def vehicle_guided_safe(self):
        if config.AUTO_GUIDED:
            self.vehicle_guided()
            return True
        for x in range(0, config.RC_WAIT_TIMEOUT):
            if self.vehicle.mode.name == "GUIDED":
                print "GUIDED mode received!"
                self.sio.emit("response", "GUIDED mode switched!")
                return True
            print "Waiting for GUIDED mode..."
            self.sio.emit("response", {'data': "Waiting for GUIDED mode..."})
            time.sleep(1)
        print "RC Input wait timed out! Vehicle will not be armed!"
        self.sio.emit("response", {'data': "RC Input wait timed out!"})
        return False

    def arm_direct(self):
        self.vehicle.armed = True

        arm_fail = 0
        while not self.vehicle.armed:
            arm_fail += 1
            if arm_fail > config.ARM_FAIL_NUMBER:
                print "Failed to arm"
                self.sio.emit('response', {'data': "Failed to arm"})
                break
            print "Waiting for arming..."
            self.sio.emit('response', {'data': "Waiting for arming..."})
            time.sleep(1)

        if self.vehicle.armed:
            print "ARMED"
            self.sio.emit('response', {'data': "ARMED"})

    def arm(self):
        if not self.success:
            return []

        if not self.vehicle_guided_safe():
            return []

        if config.DO_PRE_ARM:
            if not self.pre_arm_check():
                return []
        self.arm_direct()

    def disarm(self):
        disarm_fail = 0
        while self.vehicle.armed:
            if disarm_fail > config.ARM_FAIL_NUMBER:
                print "Failed to disarm!"
                self.sio.emit('response', {'data': "Failed to disarm!"})
            self.vehicle.armed = False
            print "Waiting for disarming..."
            self.sio.emit('response', {'data': "Waiting for disarming..."})
            time.sleep(1)

    def arm_and_takeoff(self, alt):
        if not self.success or self.taking_off:
            return []

        ascend = True
        self.taking_off = True
        self.critical = False

        if self.vehicle.armed:
            if self.vehicle.location.global_relative_frame.alt > 0.2:
                print "Already in air. Flying to altitude."
                self.sio.emit('response', {'data': "Already in air. Flying to altitude."})
                point1 = LocationGlobalRelative(self.vehicle.location.global_relative_frame.lat,
                                                self.vehicle.location.global_relative_frame.lon,
                                                alt)
                self.vehicle_guided_safe()
                if self.vehicle.mode.name == "GUIDED":
                    self.vehicle.simple_goto(point1)
                ascend = False
        else:
            self.arm()
            retry = -1
            for fails in range(0, config.ARM_RETRY_COUNT + 1):
                retry = fails
                if self.vehicle.armed:
                    if abs(self.vehicle.location.global_relative_frame.alt) >= config.DRONE_GPS_FIXER:
                        self.vehicle.simple_takeoff(alt)
                        retry -= 1
                        print "Taking off!"
                        self.sio.emit('response', {'data': "Taking off!"})
                        break
                    else:
                        if retry == config.ARM_RETRY_COUNT + 1:
                            print "Can't take off because of bad gps. Quiting."
                            self.sio.emit('response', {'data': "Can't take off because of bad gps. Quiting."})
                            break
                        print "Can't take off because of bad gps. Retry."
                        self.sio.emit('response', {'data': "Can't take off because of bad gps. Retry."})
                else:
                    print "Aborting takeoff, not armed!"
                    self.sio.emit('response', {'data': "Aborting takeoff, not armed!"})
                    break
                self.disarm()
                if self.vehicle.armed:
                    print "Aborting retry, cannot disarm!"
                    self.sio.emit('response', {'data': "Aborting retry, cannot disarm!"})
                    self.critical = True
                    break
                self.arm()

        if self.vehicle.armed and self.vehicle.mode.name == "GUIDED":
            if retry <= config.ARM_RETRY_COUNT and not self.critical:
                self.takeoff_monitor(alt, ascend)
            elif retry <= config.ARM_RETRY_COUNT:
                self.disarm()
            else:
                self.taking_off = False
        else:
            self.taking_off = False

    def takeoff_monitor(self, alt, ascend):
        fail_counter = 0
        prev_alt = 0
        times_looped = 0

        while True:
            cur_alt = self.get_location_alt()
            if times_looped == 1:
                string = "Altitude: {}".format(cur_alt)
                print string
                self.sio.emit('response', {'data': string})
                times_looped = 0
            if self._fail_check(ascend, cur_alt, prev_alt):
                fail_counter += 1

            if fail_counter > config.FAIL_COUNTERS:
                self._print_failsafe()
                if config.FAILSAFE_ON and self.vehicle.mode.name == "GUIDED":
                    self.force_loiter()
                    self._emergency()
                break

            if alt*0.95 >= cur_alt <= alt * 1.05:
                print "Reached target altitude"
                self.sio.emit('response', {'data': "Reached target altitude"})
                break

            prev_alt = cur_alt
            times_looped += 1
            time.sleep(0.5)
        self.taking_off = False

    def _fail_check(self, ascend, cur_alt, prev_alt):
        if ascend:
            if cur_alt <= prev_alt:
                return True
        else:
            if cur_alt >= prev_alt:
                return True
        return False

    def _print_failsafe(self):
        failsafe_string = ""
        if config.FAILSAFE_ON:
            failsafe_string = "Switching to LOITER"
        fail_string = "Taking off is experiencing difficulties!{}".format(failsafe_string)
        print fail_string
        self.sio.emit('response', {'data': fail_string})

    def _emergency(self):
        while self.vehicle.armed:
            self.sio.emit('response', {'data': '<font color="red"> EMERGENCY </font> Blocking commands in thread!'})
            time.sleep(1)

    def set_airspeed(self, air_speed):
        self.vehicle.airspeed = air_speed

    def force_land(self):
        self.vehicle.mode = VehicleMode("LAND")
        print "FORCE Landing"
        self.sio.emit('response', {'data': "FORCE Landing"})
        time.sleep(1)

    def force_loiter(self):
        self.vehicle.mode = VehicleMode("LOITER")
        print "FORCE Loiter"
        self.sio.emit('response', {'data': "FORCE Loiter"})
        time.sleep(1)

    def force_RTL(self):
        self.vehicle.mode = VehicleMode("RTL")
        self.sio.emit('response', {'data': "FORCE Returning To Launch"})
        time.sleep(1)

    def emergency_disarm(self):
        # APM 3.3 or later
        cmd = Command(0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                      mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 0, 21196, 0, 0, 0, 0, 0, 0)
        self.cmds.add(cmd)
        self.mission_upload()

    def print_location(self):
        string = "Altitude: {}".format(self.get_location_alt())
        print string
        self.sio.emit('response', {'data': string})

    def get_location_alt(self):
        return self.vehicle.location.global_relative_frame.alt

    def _takeoff_fail(self):
        print 'Currently taking off. Cannot takeoff again.'
        self.sio.emit('response', {'data': 'Currently taking off. Cannot takeoff again.'})

    def remove_critical(self):
        self.critical = False

    def remove_taking_off(self):
        self.taking_off = False

    def remove_bad_status(self):
        self.remove_critical()
        self.remove_taking_off()
