#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Hubitat - Plugin © Autolog 2021
#


# noinspection PyUnresolvedReferences
# ============================== Native Imports ===============================
from datetime import datetime
import logging
import platform
import socket
import sys
import threading


# ============================== Custom Imports ===============================
try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

from constants import *
from hubHandler import ThreadHubHandler

# ================================== Header ===================================
__author__    = u"Autolog"
__copyright__ = u""
__license__   = u"MIT"
__build__     = u"unused"
__title__     = u"Hubitat Plugin for Indigo"
__version__   = u"unused"


class Plugin(indigo.PluginBase):

    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        super(Plugin, self).__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)

        self.computer_name = socket.gethostbyaddr(socket.gethostname())[0].split(".")[0]  # Used in creation of MQTT Client Id

        logging.addLevelName(K_LOG_LEVEL_TOPIC, "topic")

        def topic(self, message, *args, **kws):
            # if self.isEnabledFor(K_LOG_LEVEL_TOPIC):
            # Yes, logger takes its '*args' as 'args'.
            self.log(K_LOG_LEVEL_TOPIC, message, *args, **kws)

        logging.Logger.topic = topic

        # Initialise dictionary to store plugin Globals
        self.globals = dict()

        # Initialise Indigo plugin info
        self.globals[K_PLUGIN_INFO] = {}
        self.globals[K_PLUGIN_INFO][K_PLUGIN_ID] = plugin_id
        self.globals[K_PLUGIN_INFO][K_PLUGIN_DISPLAY_NAME] = plugin_display_name
        self.globals[K_PLUGIN_INFO][K_PLUGIN_VERSION] = plugin_version
        self.globals[K_PLUGIN_INFO][K_PATH] = indigo.server.getInstallFolderPath()
        self.globals[K_PLUGIN_INFO][K_API_VERSION] = indigo.server.apiVersion
        self.globals[K_PLUGIN_INFO][K_ADDRESS] = indigo.server.address

        log_format = logging.Formatter("%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s", datefmt="%Y-%m-%d %H:%M:%S")
        self.plugin_file_handler.setFormatter(log_format)
        self.plugin_file_handler.setLevel(K_LOG_LEVEL_INFO)  # Logging Level for plugin log file
        self.indigo_log_handler.setLevel(K_LOG_LEVEL_INFO)   # Logging level for Indigo Event Log

        self.logger = logging.getLogger("Plugin.Hubitat")

        # Now logging is set-up, output Initialising Message
        startup_message_ui = "\n"  # Start with a line break
        startup_message_ui += u"{0:={1}130}\n".format(" Initialising Hubitat Plugin ", "^")
        startup_message_ui += u"{0:<31} {1}\n".format("Plugin Name:", self.globals[K_PLUGIN_INFO][K_PLUGIN_DISPLAY_NAME])
        startup_message_ui += u"{0:<31} {1}\n".format("Plugin Version:", self.globals[K_PLUGIN_INFO][K_PLUGIN_VERSION])
        startup_message_ui += u"{0:<31} {1}\n".format("Plugin ID:", self.globals[K_PLUGIN_INFO][K_PLUGIN_ID])
        startup_message_ui += u"{0:<31} {1}\n".format("Indigo Version:", indigo.server.version)
        startup_message_ui += u"{0:<31} {1}\n".format("Indigo API Version:", indigo.server.apiVersion)
        startup_message_ui += u"{0:<31} {1}\n".format("Python Version:", sys.version.replace("\n", ""))
        startup_message_ui += u"{0:<31} {1}\n".format("Mac OS Version:", platform.mac_ver()[0])
        startup_message_ui += u"{0:={1}130}\n".format("", "^")
        self.logger.info(startup_message_ui)

        # Set Plugin Config Values
        self.closedPrefsConfigUi(plugin_prefs, False)

        self.globals[HE_HUBS] = dict()

        for dev in indigo.devices.iter("self"):
            if dev.deviceTypeId == "hubitatElevationHub":  # Only process if Hub
                if dev.enabled:
                    props = dev.ownerProps
                    hubitat_hub_name = props["hub_name"]
                    if hubitat_hub_name not in self.globals[HE_HUBS]:
                        self.globals[HE_HUBS][hubitat_hub_name] = dict()
                        self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES] = dict()

    def actionControlDevice(self, action, dev):
        try:
            if not dev.enabled:
                return

            dev_id = dev.id

            dev_props = dev.pluginProps
            if "hubitatDevice" in dev_props:
                hubitat_device = dev_props["hubitatDevice"]
                hubitat_hub_dev_id = int(dev_props.get("hubitatHubId", 0))
            elif "linkedHubitatDevice" in dev_props:
                hubitat_device = dev_props["linkedHubitatDevice"]
                linked_indigo_device_id = int(dev_props.get("linkedIndigoDeviceId", 0))
                linked_indigo_dev = indigo.devices[linked_indigo_device_id]
                linked_dev_props = linked_indigo_dev.pluginProps
                hubitat_hub_dev_id = int(linked_dev_props.get("hubitatHubId", 0))
            else:
                self.logger.warning(u"Unable to perform '{0}' action for '{1}' as unable to resolve Hubitat Hub device.".format(action.description, dev.name))
                return

            if hubitat_hub_dev_id > 0:
                hub_props = indigo.devices[hubitat_hub_dev_id].ownerProps
                hubitat_hub_name = hub_props["hub_name"]

                if not self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_INITIALISED]:
                    self.logger.warning(u"Unable to perform '{0}' action for '{1}' as Hubitat Hub device '{2}' is not initialised.".format(action.description, dev.name, hubitat_hub_name))
                    return

                topic = u"{0}/{1}/{2}/onoff/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/onoff/set"

                # ##### TURN ON ######
                if action.deviceAction == indigo.kDeviceAction.TurnOn:
                    # TODO: Put in a check for if already on
                    if dev.deviceTypeId == "dimmer" or dev.deviceTypeId == "outlet":
                        dev.updateStateOnServer(key="onOffState", value=True)
                        self.logger.info(u"sent \"{0}\" on".format(dev.name))
                        topic_payload = "true"
                        self.publish_topic(hubitat_hub_name, topic, topic_payload)
                    elif dev.deviceTypeId == "valveSubModel":
                        valve_level = 50  # Assume 50% open
                        if HE_STATE_VALVE_LEVEL in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device][HE_STATES]:
                            try:
                                saved_valve_level = self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device][HE_STATES][HE_STATE_VALVE_LEVEL]
                                if saved_valve_level > 0:
                                    valve_level = saved_valve_level
                            except ValueError:
                                pass
                        dev_id_list = indigo.device.getGroupList(dev_id)
                        if len(dev_id_list) == 1:
                            return
                        thermostat_dev_id = 0
                        for linked_dev_id in dev_id_list:
                            if linked_dev_id != dev_id:
                                thermostat_dev_id = linked_dev_id
                        if thermostat_dev_id == 0:
                            return
                        thermostat_dev = indigo.devices[thermostat_dev_id]
                        hvac_state = thermostat_dev.states["hvacState"]

                        if hvac_state != "Direct Valve Control":
                            topic = u"{0}/{1}/{2}/mode/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/trv-valve/mode/set"
                            topic_payload = u"off"  # Forces TRV into "Direct Valve Control"
                            self.publish_topic(hubitat_hub_name, topic, topic_payload)
                        topic = u"{0}/{1}/{2}/dim/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/trv-valve/dim/set"
                        topic_payload = u"{0}".format(valve_level)
                        self.publish_topic(hubitat_hub_name, topic, topic_payload)

                        self.logger.info(u"sent \"{0}\" Open Valve".format(dev.name))

                # ##### TURN OFF ######
                elif action.deviceAction == indigo.kDeviceAction.TurnOff:
                    # TODO: Put in a check for if already off
                    if dev.deviceTypeId == "dimmer" or dev.deviceTypeId == "outlet":
                        dev.updateStateOnServer(key="onOffState", value=False)
                        self.logger.info(u"sent \"{0}\" off".format(dev.name))
                        topic_payload = "false"
                        self.publish_topic(hubitat_hub_name, topic, topic_payload)
                    elif dev.deviceTypeId == "valveSubModel":
                        dev_id_list = indigo.device.getGroupList(dev_id)
                        if len(dev_id_list) == 1:
                            return
                        thermostat_dev_id = 0
                        for linked_dev_id in dev_id_list:
                            if linked_dev_id != dev_id:
                                thermostat_dev_id = linked_dev_id
                        if thermostat_dev_id == 0:
                            return
                        thermostat_dev = indigo.devices[thermostat_dev_id]

                        self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device][HE_STATES][HE_STATE_VALVE_LEVEL] = dev.brightness
                        hvac_state = thermostat_dev.states["hvacState"]
                        if hvac_state != "Direct Valve Control":
                            topic = u"{0}/{1}/{2}/mode/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/trv-valve/mode/set"
                            topic_payload = u"off"  # Forces TRV into "Direct Valve Control"
                            self.publish_topic(hubitat_hub_name, topic, topic_payload)
                        topic = u"{0}/{1}/{2}/dim/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/trv-valve/dim/set"
                        topic_payload = u"0"  # Close the valve = 0% open
                        self.publish_topic(hubitat_hub_name, topic, topic_payload)

                        self.logger.info(u"sent \"{0}\" Close Valve".format(dev.name))

                # ##### TOGGLE ######
                elif action.deviceAction == indigo.kDeviceAction.Toggle:
                    if dev.onState:
                        dev.updateStateOnServer(key="onOffState", value=False)
                        self.logger.info(u"sent \"{0}\" toggle off".format(dev.name))
                        topic_payload = "false"
                        self.publish_topic(hubitat_hub_name, topic, topic_payload)
                    else:
                        dev.updateStateOnServer(key="onOffState", value=True)
                        self.logger.info(u"sent \"{0}\" toggle on".format(dev.name))
                        topic_payload = "true"
                        self.publish_topic(hubitat_hub_name, topic, topic_payload)

                # ##### SET BRIGHTNESS ######
                elif action.deviceAction == indigo.kDeviceAction.SetBrightness:
                    if dev.deviceTypeId == "dimmer":
                        new_brightness = int(action.actionValue)   # action.actionValue contains brightness value (0 - 100)
                        action_ui = u"set"
                        if new_brightness > 0:
                            if new_brightness > dev.brightness:
                                action_ui = u"brighten"
                            else:
                                action_ui = u"dim"
                        new_brightness_ui = u"{0}%".format(new_brightness)

                        topic = u"{0}/{1}/{2}/dim/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/dim/set"
                        topic_payload = u"{0}".format(new_brightness)
                        self.publish_topic(hubitat_hub_name, topic, topic_payload)

                        self.logger.info(u"sent \"{0}\" {1} to {2}".format(dev.name, action_ui, new_brightness_ui))

                    elif dev.deviceTypeId == "valveSubModel":
                        new_valve_level = int(action.actionValue)  # action.actionValue contains brightness value (0 - 100)
                        action_ui = u"set"
                        if new_valve_level > 0:
                            if new_valve_level > dev.brightness:
                                action_ui = u"open"
                            else:
                                action_ui = u"close"
                        new_brightness_ui = u"{0}%".format(new_valve_level)

                        if new_valve_level > 99:
                            new_valve_level = 99  # Fix for Eurotronic Spirit where 99 = 100 !!!

                        topic = u"{0}/{1}/{2}/dim/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/dim/set"
                        topic_payload = u"{0}".format(new_valve_level)
                        self.publish_topic(hubitat_hub_name, topic, topic_payload)

                        self.logger.info(u"sent \"{0}\" {1} to {2}".format(dev.name, action_ui, new_brightness_ui))

                # # ##### BRIGHTEN BY ######
                elif action.deviceAction == indigo.kDeviceAction.BrightenBy:
                    # if not dev.onState:
                    #     pass  # TODO: possibly turn on?
                    if dev.deviceTypeId == "dimmer":
                        if dev.brightness < 100:
                            brighten_by = int(action.actionValue)  # action.actionValue contains brightness increase value
                            new_brightness = dev.brightness + brighten_by
                            if new_brightness > 100:
                                new_brightness = 100
                            brighten_by_ui = u"{0}%".format(brighten_by)
                            new_brightness_ui = u"{0}%".format(new_brightness)

                            topic = u"{0}/{1}/{2}/dim/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/dim/set"
                            topic_payload = u"{0}".format(new_brightness)
                            self.publish_topic(hubitat_hub_name, topic, topic_payload)
                            self.logger.info(u"sent \"brighten\" {0} by {1} to {2}".format(dev.name, brighten_by_ui, new_brightness_ui))
                        else:
                            self.logger.info(u"Ignoring Brighten request for {0} as device is already at full brightness"
                                             .format(dev.name))

                    elif dev.deviceTypeId == "valveSubModel":
                        if dev.brightness < 99:  # Fix for Eurotronic Spirit where 99 = 100 !!!
                            open_by = int(action.actionValue)  # action.actionValue contains brightness increase value
                            new_valve_level = dev.brightness + open_by
                            if new_valve_level > 100:
                                new_valve_level = 100
                            brighten_by_ui = u"{0}%".format(open_by)
                            new_brightness_ui = u"{0}%".format(new_valve_level)
                            if new_valve_level > 99:
                                new_valve_level = 99  # Fix for Eurotronic Spirit where 99 = 100 !!!

                            topic = u"{0}/{1}/{2}/dim/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/dim/set"
                            topic_payload = u"{0}".format(new_valve_level)
                            self.publish_topic(hubitat_hub_name, topic, topic_payload)
                            self.logger.info(u"sent \"open valve\" {0} by {1} to {2}".format(dev.name, brighten_by_ui, new_brightness_ui))
                        else:
                            self.logger.info(u"Ignoring Open Valve request for {0} as device is already fully open"
                                             .format(dev.name))

                # ##### DIM BY ######
                elif action.deviceAction == indigo.kDeviceAction.DimBy:
                    if dev.deviceTypeId == "dimmer":
                        if dev.onState and dev.brightness > 0:
                            dim_by = int(action.actionValue)  # action.actionValue contains brightness decrease value
                            new_brightness = dev.brightness - dim_by
                            if new_brightness < 0:
                                new_brightness = 0

                                topic = u"{0}/{1}/{2}/dim/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/dim/set"
                                topic_payload = u"{0}".format(new_brightness)
                                self.publish_topic(hubitat_hub_name, topic, topic_payload)
                                topic = u"{0}/{1}/{2}/onoff/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/onoff/set"
                                topic_payload = "false"
                                self.publish_topic(hubitat_hub_name, topic, topic_payload)
                                self.logger.info(u"sent \"{0}\"' dim to off".format(dev.name))

                            else:
                                dim_by_ui = u"{0}%".format(dim_by)
                                new_brightness_ui = u"{0}%".format(new_brightness)

                                topic = u"{0}/{1}/{2}/dim/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/dim/set"
                                topic_payload = u"{0}".format(new_brightness)
                                self.publish_topic(hubitat_hub_name, topic, topic_payload)
                                self.logger.info(u"sent \"dim\" {0} by {1} to {2}".format(dev.name, dim_by_ui, new_brightness_ui))

                        else:
                            self.logger.info(u"Ignoring Dim request for '{0}'' as device is already Off".format(dev.name))

                    elif dev.deviceTypeId == "valveSubModel":
                        if dev.onState and dev.brightness > 0:
                            close_by = int(action.actionValue)  # action.actionValue contains brightness decrease value
                            new_valve_level = dev.brightness - close_by
                            if new_valve_level < 0:
                                new_valve_level = 0

                                topic = u"{0}/{1}/{2}/dim/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/dim/set"
                                topic_payload = u"{0}".format(new_valve_level)
                                self.publish_topic(hubitat_hub_name, topic, topic_payload)
                                topic = u"{0}/{1}/{2}/onoff/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/onoff/set"
                                topic_payload = "false"
                                self.publish_topic(hubitat_hub_name, topic, topic_payload)
                                self.logger.info(u"sent \"{0}\"' close valve".format(dev.name))

                            else:
                                dim_by_ui = u"{0}%".format(close_by)
                                new_brightness_ui = u"{0}%".format(new_valve_level)

                                topic = u"{0}/{1}/{2}/dim/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/dim/set"
                                topic_payload = u"{0}".format(new_valve_level)
                                self.publish_topic(hubitat_hub_name, topic, topic_payload)
                                self.logger.info(u"sent \"dim\" {0} by {1} to {2}".format(dev.name, dim_by_ui, new_brightness_ui))

                        else:
                            self.logger.info(u"Ignoring Close Valve request for '{0}'' as device is already closed".format(dev.name))

                # ##### SET COLOR LEVELS ######
                elif action.deviceAction == indigo.kDeviceAction.SetColorLevels:
                    self.process_set_color_levels(action, dev, hubitat_hub_name)

                else:
                    self.logger.warning(u"Unhandled \"actionControlDevice\" action \"{0}\" for \"{1}\"".format(action.deviceAction, dev.name))

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'actionControlDevice'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    def actionControlThermostat(self, action, dev):
        try:
            if not dev.enabled:
                return

            dev_id = dev.id

            dev_props = dev.pluginProps
            if "hubitatDevice" in dev_props:
                hubitat_device = dev_props["hubitatDevice"]
                hubitat_hub_dev_id = int(dev_props.get("hubitatHubId", 0))
            elif "linkedHubitatDevice" in dev_props:
                hubitat_device = dev_props["linkedHubitatDevice"]
                linked_indigo_device_id = int(dev_props.get("linkedIndigoDeviceId", 0))
                linked_indigo_dev = indigo.devices[linked_indigo_device_id]
                linked_dev_props = linked_indigo_dev.pluginProps
                hubitat_hub_dev_id = int(linked_dev_props.get("hubitatHubId", 0))
            else:
                self.logger.warning(u"Unable to perform '{0}' action for '{1}' as unable to resolve Hubitat Hub device.".format(action.description, dev.name))
                return

            if hubitat_hub_dev_id > 0:
                hub_props = indigo.devices[hubitat_hub_dev_id].ownerProps
                hubitat_hub_name = hub_props["hub_name"]

                if not self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_INITIALISED]:
                    return

                if (action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint or
                        action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint or
                        action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint):

                    heating_setpoint = float(dev.states["setpointHeat"])
                    if action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
                        heating_setpoint = heating_setpoint + float(action.actionValue)
                        thermostat_action_ui = "increase"
                    elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
                        heating_setpoint = heating_setpoint - float(action.actionValue)
                        thermostat_action_ui = "decrease"
                    else:
                        # action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint
                        thermostat_action_ui = "set"
                    topic_payload = u"{0}".format(heating_setpoint)
                    topic = u"{0}/{1}/{2}/heating-setpoint/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-socket-spare/heating-setpoint/set"
                    self.publish_topic(hubitat_hub_name, topic, topic_payload)
                    self.logger.info(u"sent {0} \"{1} setpoint\" to {2}".format(dev.name, thermostat_action_ui, heating_setpoint))

                elif action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
                    if action.actionMode == indigo.kHvacMode.Off:
                        topic = u"{0}/{1}/{2}/onoff/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-test-trv/onoff/set"
                        topic_payload = u"false"
                        self.publish_topic(hubitat_hub_name, topic, topic_payload)
                        self.logger.info(u"sent {0} \"set hvac mode\" to Switched Off".format(dev.name))
                    elif action.actionMode in (indigo.kHvacMode.HeatCool, indigo.kHvacMode.Heat, indigo.kHvacMode.Cool):
                        if action.actionMode == indigo.kHvacMode.HeatCool:
                            topic_payload = u"auto"
                        elif action.actionMode == indigo.kHvacMode.Heat:
                            topic_payload = u"heat"
                        elif action.actionMode == indigo.kHvacMode.Cool:
                            topic_payload = u"cool"
                        else:
                            return
                        topic_payload_ui = topic_payload
                        if topic_payload == u"cool":
                            topic_payload_ui = u"eco"

                        topic = u"{0}/{1}/{2}/mode/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-test-trv/mode/set"
                        self.publish_topic(hubitat_hub_name, topic, topic_payload)

                        self.logger.info(u"sent {0} \"set hvac mode\" to \n{1}\n".format(dev.name, topic_payload_ui))

                else:
                    self.logger.warning(u"Action '{0}' on device '{1} is not supported by the plugin.".format(action.thermostatAction, dev.name))
                    return

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'actionControlThermostat'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    def actionControlUniversal(self, action, dev):
        try:
            if not dev.enabled:
                return
            self.logger.warning(u"Action '{0}' on device '{1} is not supported by the plugin.".format(action.deviceAction, dev.name))

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'actionControlUniversal'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    def closedDeviceConfigUi(self, values_dict=None, user_cancelled=False, type_id="", dev_id=0):
        """
        Indigo method invoked after device configuration dialog is closed.

        -----
        :param values_dict:
        :param user_cancelled:
        :param type_id:
        :param dev_id:
        :return:
        """

        dev = indigo.devices[int(dev_id)]  # dev is not currently used.

        try:
            if user_cancelled:
                self.logger.threaddebug(u"'closedDeviceConfigUi' called with userCancelled = {0}".format(str(user_cancelled)))
                return

            # Code below reserved for future use


            if type_id == "button":
                pass
            elif type_id == "contactSensor":
                pass
            elif type_id == "dimmer":
                pass
            elif type_id == "motionSensor":
                pass
            elif type_id == "multiSensor":
                pass
            elif type_id == "outlet":
                pass
            elif type_id == "temperatureSensor":
                pass
            elif type_id == "thermostat":
                pass
            elif type_id == "accelerationSensorSubModel":
                pass
            elif type_id == "illuminanceSensorSubModel":
                pass
            elif type_id == "motionSensorSubModel":
                pass
            elif type_id == "pressureSensorSubModel":
                pass
            elif type_id == "temperatureSensorSubModel":
                pass
            elif type_id == "valveSubModel":
                pass
            elif type_id == "voltageSubModel":
                pass

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'closedDeviceConfigUi'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    def closedPrefsConfigUi(self, values_dict=None, user_cancelled=False):
        try:
            if user_cancelled:
                return

            # Get required Event Log and Plugin Log logging levels
            plugin_log_level = int(values_dict.get("pluginLogLevel", K_LOG_LEVEL_INFO))
            event_log_level = int(values_dict.get("eventLogLevel", K_LOG_LEVEL_INFO))

            # Ensure following logging level messages are output
            self.indigo_log_handler.setLevel(K_LOG_LEVEL_INFO)
            self.plugin_file_handler.setLevel(K_LOG_LEVEL_INFO)

            # Output required logging levels and TP Message Monitoring requirement to logs
            self.logger.info(u"Logging to Indigo Event Log at the '{0}' level".format(K_LOG_LEVEL_TRANSLATION[event_log_level]))
            self.logger.info(u"Logging to Plugin Event Log at the '{0}' level".format(K_LOG_LEVEL_TRANSLATION[plugin_log_level]))

            # Now set required logging levels
            self.indigo_log_handler.setLevel(event_log_level)
            self.plugin_file_handler.setLevel(plugin_log_level)

            self.globals[HE_MQTT_FILTERS] = dict()  # Initialise MQTT filter dictionary
            if "mqttMessageFilter" in values_dict:
                filtering_required = False
                for entry in values_dict["mqttMessageFilter"]:
                    if entry.split("|||")[0] != "-":  # Ignore '-- Select Hubitat Device(s) --' entry
                        self.globals[HE_MQTT_FILTERS][entry] = True
                        filtering_required = True

                if filtering_required:
                    log_message = u"\n\nMQTT Topic Filtering active for following Hubitat device(s):"
                    for entry in self.globals[HE_MQTT_FILTERS].iterkeys():
                        if entry.split("|||")[0] != "-":  # Ignore '-- Select Hubitat Device(s) --' entry
                            hubitat_hub_name, hubitat_device_name = entry.split("|||")
                            log_message = u"{0}\n          Hubitat Hub: '{1}', Hubitat Device: '{2}'".format(log_message, hubitat_hub_name, hubitat_device_name)
                    self.logger.warning("{0}\n".format(log_message))

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'closedPrefsConfigUi'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))
            return True

    def deviceStartComm(self, dev):
        try:
            dev.stateListOrDisplayStateIdChanged()  # Ensure latest devices.xml is being used

            if dev.deviceTypeId == "hubitatElevationHub":  # Only process if Hub
                if dev.enabled:
                    dev.updateStateOnServer(key='status', value="Disconnected")
                    dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                    dev.updateStateOnServer(key='lastTopic', value="")
                    dev.updateStateOnServer(key='lastPayload', value="")

                    hub_props = indigo.devices[dev.id].ownerProps
                    hubitat_hub_name = hub_props["hub_name"]
                    if hubitat_hub_name not in self.globals[HE_HUBS]:
                        self.globals[HE_HUBS][hubitat_hub_name] = dict()
                    if HE_MQTT_FILTER_DEVICES not in self.globals[HE_HUBS][hubitat_hub_name]:
                        self.globals[HE_HUBS][hubitat_hub_name][HE_MQTT_FILTER_DEVICES] = list()
                    self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_INDIGO_DEVICE_ID] = dev.id
                    if HE_DEVICES not in self.globals[HE_HUBS][hubitat_hub_name]:
                        self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES] = dict()
                    self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_BROKER_IP] = hub_props["mqtt_broker_ip"]
                    self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_BROKER_PORT] = int(hub_props["mqtt_broker_port"])
                    self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_CLIENT] = None
                    self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_CLIENT_ID] = u"{0}-INDIGO-HUBITAT-{1}".format(self.computer_name.upper(), hubitat_hub_name.upper())
                    self.logger.debug(u"MQTT CLIENT ID: {0}".format(self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_CLIENT_ID]))
                    self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_MESSAGE_SEQUENCE] = 0
                    self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_TOPIC] = u"{0}/{1}/#".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name)
                    self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_INITIALISED] = False

                    self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_EVENT] = threading.Event()
                    self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_THREAD] = ThreadHubHandler(self.globals, dev.id, self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_EVENT])
                    self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_THREAD].start()
            else:
                # Process Indigo Hubitat Elevation device

                # Make Sure that device address is correct and also on related sub-models
                dev_props = dev.pluginProps
                hubitat_device = dev_props.get("hubitatDevice", "")
                if hubitat_device != "":
                    if dev.address != hubitat_device:
                        self.logger.warning(u"Indigo Primary Device {0} address updated from '{1} to '{2}".format(dev.name, dev.address, hubitat_device))
                        dev_props["address"] = hubitat_device
                        dev.replacePluginPropsOnServer(dev_props)
                else:
                    member_of_device_group = bool(dev_props.get("member_of_device_group", False))
                    if member_of_device_group:
                        dev_id_list = indigo.device.getGroupList(dev.id)
                        if len(dev_id_list) > 1:
                            for linked_dev_id in dev_id_list:
                                if linked_dev_id != dev.id:
                                    linked_dev = indigo.devices[linked_dev_id]
                                    linked_props = linked_dev.pluginProps
                                    hubitat_device = linked_props.get("hubitatDevice", "")
                                    if hubitat_device != "":
                                        if dev.address != hubitat_device:
                                            self.logger.warning(u"Indigo Sub-Model Device {0} address updated from '{1} to '{2}'".format(dev.name, dev.address, hubitat_device))
                                            dev_props["address"] = hubitat_device
                                            dev.replacePluginPropsOnServer(dev_props)

                if "hubitatPropertiesInitialised" not in dev_props or not dev_props["hubitatPropertiesInitialised"]:
                    self.logger.warning(u"Hubitat Device {0} has not been initialised - Edit and Save device Settings for device.".format(dev.name))
                    return

                hubitat_hub_dev_id = int(dev_props.get("hubitatHubId", 0))
                if hubitat_hub_dev_id <= 0:
                    self.logger.warning(u"No Hubitat Elevation Hub has been associated with hubitat device '{0}'".format(dev.name))
                    return
                if hubitat_hub_dev_id not in indigo.devices:
                    self.logger.warning(u"Hubitat Elevation Hub no longer associated with hubitat device '{0}'".format(dev.name))
                    return

                hub_props = indigo.devices[hubitat_hub_dev_id].ownerProps
                hubitat_hub_name = hub_props["hub_name"]

                if hubitat_hub_name not in self.globals[HE_HUBS]:
                    self.logger.warning(u"Hubitat Elevation Hub '{0}' associated with hubitat device '{1}' is unknown or disabled".format(hubitat_hub_name, dev.name))
                    return

                self.process_sub_models(dev, hubitat_hub_dev_id)  # Check if Sub-Model(s) required to be created and create as necessary

                dev_props = dev.pluginProps
                if "linkedHubitatDevice" in dev_props and dev_props.get("linkedHubitatDevice", "") != "":
                    hubitat_device = dev_props["linkedHubitatDevice"]
                else:
                    hubitat_device = dev_props["hubitatDevice"]

                if hubitat_device not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES]:
                    self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device] = dict()  # Hubitat device name
                if HE_LINKED_INDIGO_DEVICES not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device]:
                    self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device][HE_LINKED_INDIGO_DEVICES] = dict()
                self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device][HE_LINKED_INDIGO_DEVICES][dev.id] = dev.id
                if HE_PROPERTIES not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device]:
                    self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device][HE_PROPERTIES] = None
                if self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device][HE_PROPERTIES] is None:
                    stored_hubitat_properties = dev_props.get("storedHubitatDeviceProperties", "")
                    if stored_hubitat_properties != "":
                        self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device][HE_PROPERTIES] = stored_hubitat_properties

                if HE_DEVICE_DRIVER not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device]:
                    self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device][HE_DEVICE_DRIVER] = None

                # TODO: Set image for UI depending on deviceTypeId

            self.logger.info(u"Device '{0}' Started".format(dev.name))

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'deviceStartComm' for device '{0}'. Line '{1}' has error='{2}'"
                              .format(dev.name, sys.exc_traceback.tb_lineno, standard_error_message))

    def deviceStopComm(self, dev):
        try:
            self.logger.info(u"Device '{0}' Stopped".format(dev.name))

            if dev.deviceTypeId == "hubitatElevationHub":
                hub_props = dev.ownerProps
                hubitat_hub_name = hub_props["hub_name"]

                self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_EVENT].set()  # Stop the Hub handler Thread
                self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_THREAD].join(5.0)  # Wait for up t0 5 seconds for it to end
                # Delete thread so that it can be recreated if Hubitat Elevation Hub devices is turned on again
                del self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_THREAD]

                self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_INITIALISED] = False

                return

            # As Hubitat device is being stopped - delete its id from internal Hubitat Devices table.

            dev_props = dev.pluginProps

            hubitat_hub_id = int(dev_props.get("hubitatHubId", 0))
            if hubitat_hub_id <= 0:
                self.logger.debug(u"No Hubitat Elevation Hub has been associated with hubitat device '{0}'".format(dev.name))
                return
            if hubitat_hub_id not in indigo.devices:
                self.logger.debug(u"Hubitat Elevation Hub no longer associated with hubitat device '{0}'".format(dev.name))
                return
            hub_props = indigo.devices[hubitat_hub_id].ownerProps
            hubitat_hub_name = hub_props["hub_name"]
            if hubitat_hub_name not in self.globals[HE_HUBS]:
                self.logger.debug(u"Hubitat Elevation Hub '{0}' associated with hubitat device '{1}' is unknown or disabled".format(hubitat_hub_name, dev.name))
                return

            dev_props = dev.pluginProps
            hubitat_device = dev_props.get("hubitatDevice", "")  # Allows for entry not being present in Sub-Models
            if hubitat_device in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES]:
                if HE_LINKED_INDIGO_DEVICES in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device]:
                    if dev.id in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device][HE_LINKED_INDIGO_DEVICES]:
                        del self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device][HE_LINKED_INDIGO_DEVICES][dev.id]

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'deviceStopComm'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    def deviceUpdated(self, origDev, newDev):
        try:
            if origDev.deviceTypeId == "dimmer":
                if "whiteLevel" in newDev.states:
                    if newDev.states["whiteLevel"] != newDev.states["brightnessLevel"]:
                        white_level = newDev.states["brightnessLevel"]
                        newDev.updateStateOnServer(key='whiteLevel', value=white_level)
                        # self.logger.debug(u"Brightness: {0} vs {1}, White Level: {2} vs {3}"
                        #                     .format(origDev.states["brightnessLevel"], newDev.states["brightnessLevel"],
                        #                             origDev.states["whiteLevel"], newDev.states["whiteLevel"]))
        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'deviceUpdated'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

        super(Plugin, self).deviceUpdated(origDev, newDev)

    def getDeviceConfigUiValues(self, plugin_props, type_id="", dev_id=0):
        try:
            if type_id == "hubitatElevationHub":
                if "hub_name" not in plugin_props:
                    plugin_props["hub_name"] = ""  # Name of Hubitat Elevation Hub - "" if not present
                if "mqtt_broker_ip" not in plugin_props:
                    plugin_props["mqtt_broker_ip"] = ""  # IP of MQTT Broker - "" if not present
                if "mqtt_broker_port" not in plugin_props:
                    plugin_props["mqtt_broker_port"] = "1883"  # Port of MQTT Broker - Default = "1883" if not present

            elif type_id in ("button", "contactSensor", "motionSensor", "multiSensor", "outlet", "temperatureSensor", "thermostat", "dimmer"):
                plugin_props["primaryIndigoDevice"] = True
                if "hubitatDevice" not in plugin_props:
                    plugin_props["hubitatDevice"] = "-SELECT-"  # Name of Hubitat Elevation Device - Default: "-SELECT-", "-- Select Hubitat Device(s) --"
                if "hubitatHubId" not in plugin_props:
                    plugin_props["hubitatHubId"] = 0  # Id of Indigo Hubitat Elevation Hub device - Default: 0, "-- Select Hubitat Hub --"
                
                if "hubitatPropertiesInitialised" not in plugin_props or not plugin_props["hubitatPropertiesInitialised"]:
                    plugin_props["hubitatPropertyAcceleration"] = False
                    plugin_props["hubitatPropertyBattery"] = False
                    plugin_props["hubitatPropertyButton"] = False
                    plugin_props["hubitatPropertyColor"] = False
                    plugin_props["hubitatPropertyColorName"] = False
                    plugin_props["hubitatPropertyColorTemperature"] = False
                    plugin_props["hubitatPropertyContact"] = False
                    plugin_props["hubitatPropertyDim"] = False
                    plugin_props["hubitatPropertyEnergy"] = False
                    plugin_props["hubitatPropertyHumidity"] = False
                    plugin_props["hubitatPropertyIlluminance"] = False
                    plugin_props["hubitatPropertyHvacMode"] = False
                    plugin_props["hubitatPropertyMotion"] = False
                    plugin_props["hubitatPropertyOnOff"] = False
                    plugin_props["hubitatPropertyPower"] = False
                    plugin_props["hubitatPropertyPresence"] = False
                    plugin_props["hubitatPropertyPressure"] = False
                    plugin_props["hubitatPropertySetpoint"] = False
                    plugin_props["hubitatPropertyHvacState"] = False
                    plugin_props["hubitatPropertyTemperature"] = False
                    plugin_props["hubitatPropertyValve"] = False
                    plugin_props["hubitatPropertyVoltage"] = False

                    plugin_props["uspAcceleration"] = False
                    plugin_props["uspBattery"] = False
                    plugin_props["uspButton"] = False
                    plugin_props["uspColorRGB"] = False
                    plugin_props["uspContact"] = False
                    plugin_props["uspDimmer"] = False
                    plugin_props["uspEnergy"] = False
                    plugin_props["uspHumidity"] = False
                    plugin_props["uspHvacMode"] = False
                    plugin_props["uspHvacState"] = False
                    plugin_props["uspIlluminance"] = False
                    plugin_props["uspMotion"] = False
                    plugin_props["uspOnOff"] = False
                    plugin_props["uspPower"] = False
                    plugin_props["uspPresence"] = False
                    plugin_props["uspPressure"] = False
                    plugin_props["uspSetpoint"] = False
                    plugin_props["uspTemperature"] = False
                    plugin_props["uspValve"] = False
                    plugin_props["uspVoltage"] = False
                    plugin_props["uspWhiteTemperature"] = False

            elif type_id in ("accelerationSensorSubModel", "illuminanceSensorSubModel",
                             "motionSensorSubModel", "pressureSensorSubModel",
                             "temperatureSensorSubModel", "valveSubModel"):
                plugin_props['primaryIndigoDevice'] = False
                # The following code sets the property "member_of_device_group" to True if the SubModel (secondary) device
                #   is associated with a primary device. If not it is set to False. This property is used
                #   in Devices.xml to display a red warning box and disable device editing if set to False.
                plugin_props['member_of_device_group'] = False
                plugin_props["primaryIndigoDevice"] = False
                dev_id_list = indigo.device.getGroupList(dev_id)
                if len(dev_id_list) > 1:
                    plugin_props['member_of_device_group'] = True
                    for linked_dev_id in dev_id_list:
                        linked_dev_props = indigo.devices[linked_dev_id].ownerProps
                        primary_device = linked_dev_props.get("primaryIndigoDevice", False)
                        if primary_device:
                            plugin_props['linkedIndigoDeviceId'] = indigo.devices[linked_dev_id].id
                            plugin_props['linkedIndigoDevice'] = indigo.devices[linked_dev_id].name
                            plugin_props['linkedHubitatDevice'] = linked_dev_props["hubitatDevice"]

            return super(Plugin, self).getDeviceConfigUiValues(plugin_props, type_id, dev_id)

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'getDeviceConfigUiValues' for device '{0}'. Line '{1}' has error='{2}'"
                              .format(indigo.devices[dev_id].name, sys.exc_traceback.tb_lineno, standard_error_message))

    def getDeviceStateList(self, dev):
        try:
            self.logger.debug(u"getDeviceStateList invoked for '{0}'".format(dev.name))

            state_list = indigo.PluginBase.getDeviceStateList(self, dev)

            # Acceleration State
            if (bool(dev.pluginProps.get("uspAcceleration", False)) and
                    dev.pluginProps.get("uspAccelerationIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                acceleration_state = self.getDeviceStateDictForBoolTrueFalseType(u"acceleration", u"Acceleration Changed", u"Acceleration")
                if acceleration_state not in state_list:
                    state_list.append(acceleration_state)

            # Button State(s)
            if bool(dev.pluginProps.get("uspButton", False)):
                number_of_buttons = int(dev.pluginProps.get("uspNumberOfButtons", 1))
                for button_number in range(1, (number_of_buttons + 1)):
                    button_state_id = u"button_{0}".format(button_number)
                    button_trigger_label = u"Button {0} Changed".format(button_number)
                    button_control_page_label = u"Button {0}".format(button_number)
                    button_state = self.getDeviceStateDictForStringType(button_state_id, button_trigger_label, button_control_page_label)
                    if button_state not in state_list:
                        state_list.append(button_state)
                button_state_id = u"lastButtonPressed"
                button_trigger_label = u"Last Button Pressed Changed"
                button_control_page_label = u"Last Button Pressed"
                button_state = self.getDeviceStateDictForStringType(button_state_id, button_trigger_label, button_control_page_label)
                if button_state not in state_list:
                    state_list.append(button_state)

            # Illuminance State
            if (bool(dev.pluginProps.get("uspIlluminance", False)) and
                    dev.pluginProps.get("uspIlluminanceIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                illuminance_state = self.getDeviceStateDictForNumberType(u"illuminance", u"Illuminance Changed", u"Illuminance")
                if illuminance_state not in state_list:
                    state_list.append(illuminance_state)

            # Pressure State
            if (bool(dev.pluginProps.get("uspPressure", False)) and
                    dev.pluginProps.get("uspPressureIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                pressure_state = self.getDeviceStateDictForNumberType(u"pressure", u"Pressure Changed", u"Pressure")
                if pressure_state not in state_list:
                    state_list.append(pressure_state)

            # Presence State
            if (bool(dev.pluginProps.get("uspPresence", False)) and
                    dev.pluginProps.get("uspPresenceIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                presence_state = self.getDeviceStateDictForBoolTrueFalseType(u"presence", u"Presence Changed", u"Presence")
                if presence_state not in state_list:
                    state_list.append(presence_state)

            # Temperature State
            if (bool(dev.pluginProps.get("uspTemperature", False)) and
                    dev.pluginProps.get("uspTemperatureIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                temperature_state = self.getDeviceStateDictForNumberType(u"temperature", u"Temperature Changed", u"Temperature")
                if temperature_state not in state_list:
                    state_list.append(temperature_state)

            # Voltage State
            if (bool(dev.pluginProps.get("uspVoltage", False)) and
                    dev.pluginProps.get("uspVoltageIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                voltage_state = self.getDeviceStateDictForNumberType(u"voltage", u"Voltage Changed", u"Voltage")
                if voltage_state not in state_list:
                    state_list.append(voltage_state)

            # Color RGB
            if bool(dev.pluginProps.get("uspColorRGB", False)) or bool(dev.pluginProps.get("uspWhiteTemperature", False)):
                color_mode_state = self.getDeviceStateDictForStringType(u"colorMode", u"Color Mode Changed", u"Color Mode")
                if color_mode_state not in state_list:
                    state_list.append(color_mode_state)
                color_name_state = self.getDeviceStateDictForStringType(u"colorName", u"Color Name Changed", u"Color Name")
                if color_name_state not in state_list:
                    state_list.append(color_name_state)

            # HVAC Mode
            if bool(dev.pluginProps.get("uspHvacMode", False)):
                hvac_mode_state = self.getDeviceStateDictForStringType(u"hvacMode", u"HVAC Mode Changed", u"HVAC Mode")
                if hvac_mode_state not in state_list:
                    state_list.append(hvac_mode_state)

            # HVAC State
            if bool(dev.pluginProps.get("uspHvacState", False)):
                hvac_state_state = self.getDeviceStateDictForStringType(u"hvacState", u"HVAC Mode Changed", u"HVAC State")
                if hvac_state_state not in state_list:
                    state_list.append(hvac_state_state)

            # Motion State
            if (bool(dev.pluginProps.get("uspMotion", False)) and
                    dev.pluginProps.get("uspMotionIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                motion_state = self.getDeviceStateDictForStringType(u"motion", u"Motion Changed", u"Motion")
                if motion_state not in state_list:
                    state_list.append(motion_state)

            # Valve State
            if (bool(dev.pluginProps.get("uspValve", False)) and
                    dev.pluginProps.get("uspValveIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                valve_state = self.getDeviceStateDictForStringType(u"valve", u"Valve Changed", u"Valve")
                if valve_state not in state_list:
                    state_list.append(valve_state)

            # Voltage State
            if (bool(dev.pluginProps.get("uspVoltage", False)) and
                    dev.pluginProps.get("uspVoltageIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                voltage_state = self.getDeviceStateDictForStringType(u"voltage", u"Voltage Changed", u"Voltage")
                if voltage_state not in state_list:
                    state_list.append(voltage_state)

            self.logger.debug(u"State List [Amended]: {0}".format(state_list))
            return state_list
        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'getDeviceStateList'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    # def getPrefsConfigUiValues(self):
    #     prefs_config_ui_values = self.pluginPrefs
    #
    #     pass
    #
    #     return prefs_config_ui_values

    def refreshUiCallback(self, valuesDict, typeId="", devId=None):
        errorsDict = indigo.Dict()
        try:
            if valuesDict["hubitatHubId"] == 0:
                valuesDict["hubitatDevice"] = "-FIRST-"
            elif valuesDict["hubitatDevice"] == "":
                valuesDict["hubitatDevice"] = "-SELECT-"

            # hubitatDevice = valuesDict["hubitatDevice"]
            # hubitatHub = valuesDict["hubitatHubId"]
            # self.logger.error(u"refreshUiCallback: Hub =  '{0}' [{1}, Device = '{2}' [{3}".format(hubitatHub, type(hubitatHub), hubitatDevice, type(hubitatDevice)))

            usp_field_id_check_1 = ""
            usp_field_id_check_2 = ""
            if typeId == "button":
                usp_field_id_check_1 = "uspButtonIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "contactSensor":
                usp_field_id_check_1 = "uspContactIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "dimmer":
                usp_field_id_check_1 = "uspDimmerIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
                usp_field_id_check_2 = "uspOnOffIndigo"
                valuesDict[usp_field_id_check_2] = INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE
            elif typeId == "motionSensor":
                usp_field_id_check_1 = "uspMotionIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "multiSensor":
                usp_field_id_check_1 = "uspMotionIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "outlet":
                usp_field_id_check_1 = "uspOnOffIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "temperatureSensor":
                usp_field_id_check_1 = "uspTemperatureIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "thermostat":
                usp_field_id_check_1 = "uspTemperatureIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
                usp_field_id_check_2 = "uspSetpointIndigo"
                valuesDict[usp_field_id_check_2] = INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE

            for usp_field_id in ("uspAccelerationIndigo", "uspButtonIndigo" ,"uspContactIndigo", "uspDimmerIndigo",
                                 "uspEnergyIndigo", "uspHumidityIndigo", "uspIlluminanceIndigo", "uspMotionIndigo",
                                 "uspOnOffIndigo", "uspPowerIndigo", "uspPresenceIndigo", "uspPressureIndigo",
                                 "uspTemperatureIndigo", "uspSetpointIndigo", "uspValveIndigo", "uspVoltageIndigo"):
                if (usp_field_id != usp_field_id_check_1 and usp_field_id != usp_field_id_check_2 and
                        (usp_field_id not in valuesDict or
                         valuesDict[usp_field_id] not in [INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE, INDIGO_SECONDARY_DEVICE, INDIGO_SECONDARY_DEVICE_ADDITIONAL_STATE])):
                    valuesDict[usp_field_id] = INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE  # Default

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'getDeviceStateList'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

        return valuesDict, errorsDict

    def shutdown(self):
        # self.mqtt_client.disconnect()
        self.logger.info(u"Hubitat plugin shutdown invoked")

    def startup(self):
        try:
            if len(self.globals[HE_HUBS]) == 0:
                self.logger.error(u"No Hubitat Elevation Hubs have been defined as Indigo devices - plugin won't work!")
                return

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'startup'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    def stopConcurrentThread(self):
        self.logger.info(u"Hubitat plugin closing down")

    def validateDeviceConfigUi(self, values_dict=None, type_id="", dev_id=0):
        try:
            error_dict = indigo.Dict()

            if type_id == "hubitatElevationHub":
                values_dict["address"] = values_dict["hub_name"]
                return True, values_dict

            # Start of Special validation for linked devices [Sub-Models]

            if type_id not in ("button", "contactSensor", "motionSensor", "multiSensor", "outlet", "temperatureSensor", "thermostat", "dimmer"):
                return True, values_dict

            # ^^^ - End of Special validation for linked devices [Sub-Models]

            if values_dict["hubitatHubId"] == "0":
                error_dict['hubitatHubId'] = u"A Hubitat hub must be selected"
                return False, values_dict, error_dict

            if values_dict["hubitatDevice"] == "-SELECT-":
                error_dict['hubitatDevice'] = u"A Hubitat device must be selected"
                return False, values_dict, error_dict
            elif values_dict["hubitatDevice"] == "-NONE-":
                error_dict['hubitatDevice'] = u"Unable to save as no available Hubitat devices"
                return False, values_dict, error_dict
            elif values_dict["hubitatDevice"] == "-FIRST-":
                error_dict['hubitatDevice'] = u"Unable to save as no Hubitat Hub selected"
                return False, values_dict, error_dict

            values_dict["address"] = values_dict["hubitatDevice"]

            values_dict["SupportsBatteryLevel"] = False
            values_dict["NumHumidityInputs"] = 0
            values_dict["NumTemperatureInputs"] = 0
            values_dict["ShowCoolHeatEquipmentStateUI"] = False
            values_dict["SupportsCoolSetpoint"] = False
            values_dict["SupportsEnergyMeter"] = False
            values_dict["SupportsEnergyMeterCurPower"] = False
            values_dict["SupportsAccumEnergyTotal"] = False

            values_dict["SupportsHeatSetpoint"] = False
            values_dict["SupportsHvacFanMode"] = False
            values_dict["SupportsHvacOperationMode"] = False
            values_dict["SupportsOnState"] = False
            values_dict["SupportsSensorValue"] = False
            values_dict["SupportsStatusRequest"] = False
            values_dict["supportsTemperatureReporting"] = False
            values_dict["supportsValve"] = False

            values_dict["SupportsColor"] = False
            values_dict["SupportsRGB"] = False
            values_dict["SupportsWhite"] = False
            values_dict["SupportsWhiteTemperature"] = False
            values_dict["SupportsTwoWhiteLevels"] = False

            if values_dict.get("hubitatPropertyBattery", False):
                values_dict["SupportsBatteryLevel"] = True
            else:
                values_dict["SupportsBatteryLevel"] = False

            values_dict["address"] = values_dict["hubitatDevice"]

            # TODO: Use $nodes to check if device address is still valid - old nodes can be left behind in MQTT?

            if type_id == "button":
                # Scene (Button) validation and option settings
                if not values_dict.get("uspButton", False):
                    error_message = u"An Indigo Scene (Button) device requires an association to the Hubitat 'button' property"
                    error_dict['uspButton'] = error_message
                    error_dict["showAlertText"] = error_message

            elif type_id == "contactSensor":
                # Contact Sensor validation and option settings
                if not values_dict.get("uspContact", False):
                    error_message = u"An Indigo Contact Sensor device requires an association to the Hubitat 'contact' property"
                    error_dict['uspContact'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsOnState"] = True
                    values_dict["allowOnStateChange"] = False

            elif type_id == "dimmer":
                # Dimmer validation and option settings
                if not values_dict.get("uspDimmer", False):
                    error_message = u"An Indigo Dimmer device requires an association to the Hubitat 'dim' property"
                    error_dict['uspDimmer'] = error_message
                    error_dict["showAlertText"] = error_message
                elif not values_dict.get("uspOnOff", False):
                    error_message = u"An Indigo Dimmer device requires an association to the Hubitat 'onoff' property"
                    error_dict['uspOnOff'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    if bool(values_dict.get("uspColorRGB", False)):
                        values_dict["SupportsColor"] = True
                        values_dict["SupportsRGB"] = True
                    if bool(values_dict.get("uspWhiteTemperature", False)):
                        values_dict["SupportsColor"] = True
                        values_dict["SupportsWhite"] = True
                        values_dict["SupportsWhiteTemperature"] = True
                        try:
                            values_dict["WhiteTemperatureMin"] = int(values_dict.get("uspKelvinMinimum", 2500))
                        except ValueError:
                            error_message = u"Kelvin Minimum must be an integer"
                            error_dict['uspKelvinMinimum'] = error_message
                            error_dict["showAlertText"] = error_message
                        try:
                            values_dict["WhiteTemperatureMax"] = int(values_dict.get("uspKelvinMaximum", 9000))
                        except ValueError:
                            error_message = u"Kelvin Minimum must be an integer"
                            error_dict['uspKelvinMaximum'] = error_message
                            error_dict["showAlertText"] = error_message

            elif type_id == "motionSensor":
                # Motion Sensor validation and option settings
                if not values_dict.get("uspMotion", False):
                    error_message = u"An Indigo Motion Sensor device requires an association to the Hubitat 'motion' property"
                    error_dict['uspMotion'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsOnState"] = True
                    values_dict["allowOnStateChange"] = False

            elif type_id == "multiSensor":
                # Motion Sensor validation and option settings
                if not values_dict.get("uspMotion", False):
                    error_message = u"An Indigo Multi-Sensor device requires an association to the Hubitat 'motion' property"
                    error_dict['uspMotion'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsOnState"] = True
                    values_dict["allowOnStateChange"] = False

            elif type_id == "outlet":
                # Outlet (Socket) validation and option settings
                if not values_dict.get("uspOnOff", False):
                    error_message = u"An Indigo Outlet (Socket) device requires an association to the Hubitat 'onoff' property"
                    error_dict['uspOnOff'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsOnState"] = True
                    if bool(values_dict.get("uspPower", False)):
                        values_dict["SupportsEnergyMeter"] = True
                        values_dict["SupportsEnergyMeterCurPower"] = True
                    if bool(values_dict.get("uspEnergy", False)):
                        values_dict["SupportsEnergyMeter"] = True
                        values_dict["SupportsAccumEnergyTotal"] = True

            elif type_id == "thermostat":
                # Thermostat validation and option settings
                if not values_dict.get("uspTemperature", False):
                    error_message = u"An Indigo Thermostat device requires an association to the Hubitat 'temperature' property"
                    error_dict['uspTemperature'] = error_message
                    error_dict["showAlertText"] = error_message
                elif not values_dict.get("uspSetpoint", False):
                    error_message = u"An Indigo Thermostat device requires an association to the Hubitat 'setpoint' property"
                    error_dict['uspSetpoint'] = error_message
                    error_dict["showAlertText"] = error_message
                # elif not values_dict.get("uspOnOff", False):
                #     error_message = u"An Indigo Thermostat device requires an association to the Hubitat 'onoff' property"
                #     error_dict['uspOnOff'] = error_message
                #     error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsHeatSetpoint"] = True
                    values_dict["NumTemperatureInputs"] = 1
                    values_dict["supportsTemperatureReporting"] = True
                    if values_dict.get("uspHvacMode", False):
                        values_dict["SupportsHvacOperationMode"] = True
                    if (bool(values_dict.get("uspValve", False)) and
                            values_dict.get("uspValveIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_SECONDARY_DEVICE):
                        values_dict["supportsValve"] = True

            elif type_id == "temperatureSensor":
                # Thermostat validation and option settings
                if not values_dict.get("uspTemperature", False):
                    error_message = u"An Indigo Thermostat device requires an association to the Hubitat 'temperature' property"
                    error_dict['uspTemperature'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["supportsTemperatureReporting"] = True
                    values_dict["NumTemperatureInputs"] = 1
                    if (bool(values_dict.get("uspHumidity", False)) and
                            values_dict.get("uspHumidityIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                        values_dict["NumHumidityInputs"] = 1

            if (bool(values_dict.get("uspHumidity", False)) and
                    values_dict.get("uspHumidityIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_SECONDARY_DEVICE_ADDITIONAL_STATE):
                if (not bool(values_dict.get("uspTemperature", False)) or
                        values_dict.get("uspTemperatureIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) != INDIGO_SECONDARY_DEVICE):
                    error_message = u"Selecting Humidity as an additional state on a secondary device requires that an associated secondary temperature sensor device is selected."
                    error_dict['uspTemperature'] = error_message
                    error_dict['uspHumidity'] = error_message
                    error_dict["showAlertText"] = error_message

            # ============================ Process Any Errors =============================
            if len(error_dict) > 0:
                return False, values_dict, error_dict
            else:
                values_dict["hubitatPropertiesInitialised"] = True
                return True, values_dict

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'validateDeviceConfigUi' for device '{0}'. Line {1} has error='{2}'"
                              .format(indigo.devices[dev_id].name, sys.exc_traceback.tb_lineno, standard_error_message))

    #################################
    #
    # Start of bespoke plugin methods
    #
    #################################

    def listDeviceStateMenuOptions(self, filter="", valuesDict=None, typeId="", targetId=0):
        try:

            # <Option value="0">Primary Device - Main UI State</Option>
            # <Option value="1">Primary Device - Additional State</Option>
            # <Option value="2">Secondary Device</Option>
            # <Option value="2">Secondary Device - Additional State</Option>

            if ((filter == "button" and typeId == "button") or
                    (filter == "contactSensor" and typeId == "contactSensor") or
                    (filter == "dimmer" and typeId == "dimmer") or
                    (filter == "motionSensor" and typeId == "motionSensor") or
                    (filter == "motionSensor" and typeId == "multiSensor") or
                    (filter == "onoff" and typeId == "outlet") or
                    (filter == "temperatureSensor" and typeId == "temperatureSensor") or
                    (filter == "temperatureSensor" and typeId == "thermostat")):
                menu_list = [("0", "Primary Device - Main UI State")]
            elif ((filter == "setpoint" and typeId == "thermostat") or
                  (filter == "onoff" and typeId == "thermostat") or
                  (filter == "onoff" and typeId == "dimmer")):
                menu_list = [("1", "Primary Device - Additional State")]
            elif filter == "humiditySensor":
                menu_list = [("1", "Primary Device - Additional State"), ("3", "Secondary Device - Additional State")]
            else:
                menu_list = [("1", "Primary Device - Additional State"), ("2", "Secondary Device")]

            return menu_list

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'listDeviceStateMenuOptions' for device '{0}'. Line {1} has error='{2}'"
                              .format(indigo.devices[targetId].name, sys.exc_traceback.tb_lineno, standard_error_message))

    def listHubitatHubs(self, filter="", valuesDict=None, typeId="", targetId=0):
        try:
            self.logger.debug(u"List Hubitat Hubs")

            hubitat_hubs_list = list()
            hubitat_hubs_list.append((0, "-- Select Hubitat Hub --"))
            for dev in indigo.devices.iter("self"):
                if dev.deviceTypeId == "hubitatElevationHub":
                    hubitat_hubs_list.append((dev.id, dev.name))

            if len(hubitat_hubs_list) > 1:
                return sorted(hubitat_hubs_list, key=lambda name: name[1].lower())   # sort by hubitat hub name
            else:
                hubitat_hubs_list.append((-1, "No Hubitat hubs available"))
                return hubitat_hubs_list
        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'listHubitatHubs'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    def listHubitatHubSelected(self, valuesDict, typeId, devId):
        try:
            # do whatever you need to here
            #   typeId is the device type specified in the Devices.xml
            #   devId is the device ID - 0 if it's a new device
            self.logger.debug(u"Hubitat Hub Selected: {0}".format(valuesDict["hubitatHubId"]))

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'listHubitatHubSelected'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

        return valuesDict

    def listHubitatDevices(self, filter="", valuesDict=None, typeId="", targetId=0):
        try:
            hubitat_devices_list = []

            allocated_devices = dict()
            for dev in indigo.devices.iter("self"):
                if dev.id != targetId and dev.deviceTypeId in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES:
                    dev_props = dev.ownerProps
                    hubitat_device = dev_props.get("hubitatDevice", "")
                    if hubitat_device != "":
                        if hubitat_device not in allocated_devices:
                            allocated_devices[hubitat_device] = dev.id
            # self.logger.warning(u"List of allocated Devices: {0}".format(allocated_devices))

            dev = indigo.devices[targetId]

            hubitat_hub_dev_id = int(valuesDict.get("hubitatHubId", 0))

            # self.logger.debug(u"List Hubitat Devices: {0}".format(valuesDict["hubitatHubId"]))
            self.logger.debug(u"List Hubitat Devices [1]")

            if hubitat_hub_dev_id > 0 and hubitat_hub_dev_id in indigo.devices:

                hub_props = indigo.devices[hubitat_hub_dev_id].ownerProps
                hubitat_hub_name = hub_props["hub_name"]

                hubitat_devices_list.append(("-SELECT-", "-- Select Hubitat Device --"))
                for hubitat_device_name, hubitat_devices_details in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES].items():
                    # already_allocated = False
                    if hubitat_device_name in allocated_devices:
                        continue  # Continue as already allocated

                    hubitat_device_properties = list()
                    if HE_PROPERTIES in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                        if self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] is not None:
                            # self.logger.warning(u"listHubitatDevices - PROPERTIES: {0}".format(self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES]))
                            hubitat_device_properties = self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES].split(",")

                    # device_type_supported_hubitat_properties = HE_DEVICE_TYPES_MAIN_HABITAT_PROPERTIES[dev.deviceTypeId]
                    for device_type_main_hubitat_properties in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES[dev.deviceTypeId]:
                        if device_type_main_hubitat_properties in hubitat_device_properties:
                            hubitat_devices_list.append((hubitat_device_name, hubitat_device_name))
                            break

            # self.logger.error(u"ValuesDict Hubitat Device: {0}".format(valuesDict["hubitatDevice"]))  # TODO Debug Remove this
            # self.logger.warning(u"Hubitat Devices List: {0}".format(hubitat_devices_list))  # TODO Debug Remove this

            if len(hubitat_devices_list) > 1:
                return sorted(hubitat_devices_list, key=lambda name: name[1].lower())   # sort by hubitat device name
            else:
                if hubitat_hub_dev_id  == 0:
                    hubitat_devices_list = list()
                    hubitat_devices_list.append(("-FIRST-", "^^^ Select Hubitat Hub First ^^^".format(dev.model)))
                else:
                    hubitat_devices_list = list()
                    hubitat_devices_list.append(("-NONE-", "No \"{}\" devices available".format(dev.model)))
                self.logger.debug(u"List Hubitat Devices [2]: {0}".format(hubitat_devices_list))

                return hubitat_devices_list

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'listHubitatDevices'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    def listHubitatDeviceSelected(self, valuesDict, typeId, devId):
        try:
            # do whatever you need to here
            #   typeId is the device type specified in the Devices.xml
            #   devId is the device ID - 0 if it's a new device
            self.logger.debug(u"Hubitat Device Selected: {0} on Indigo Device ID {1}".format(valuesDict["hubitatDevice"], int(valuesDict.get("hubitatHubId", 0))))

            dev = indigo.devices[devId]

            hubitat_device_name = valuesDict.get("hubitatDevice", "-SELECT-")

            # hubitat_device_properties_list = []
            if hubitat_device_name == "-SELECT-" or hubitat_device_name == "-NONE-" or hubitat_device_name == "-FIRST-":
                return

            hubitat_hub_dev_id = int(valuesDict.get("hubitatHubId", 0))
            if hubitat_hub_dev_id > 0 and hubitat_hub_dev_id in indigo.devices:
                hub_props = indigo.devices[hubitat_hub_dev_id].ownerProps
                hubitat_hub_name = hub_props["hub_name"]

                hubitat_device_name = valuesDict.get("hubitatDevice", "-SELECT-")
                if hubitat_device_name != "" and hubitat_device_name in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES]:

                    valuesDict["hubitatDeviceDriver"] = "-"
                    if HE_DEVICE_DRIVER in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                        if (self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_DEVICE_DRIVER] is not None and
                                self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_DEVICE_DRIVER] != ""):
                            valuesDict["hubitatDeviceDriver"] = self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_DEVICE_DRIVER]

                    hubitat_device_properties = self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES].split(",")

                    for hubitat_device_property in hubitat_device_properties:

                        if hubitat_device_property == "acceleration":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyAcceleration"] = True
                            else:
                                valuesDict["hubitatPropertyAcceleration"] = False

                        elif hubitat_device_property == "measure-battery" or hubitat_device_property == "battery":
                            hubitat_device_property = "battery"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyBattery"] = True
                            else:
                                valuesDict["hubitatPropertyBattery"] = False

                        elif hubitat_device_property == "button":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyButton"] = True
                            else:
                                valuesDict["hubitatPropertyButton"] = False

                        elif hubitat_device_property == "dim":
                            if dev.deviceTypeId == "dimmer":
                                if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                    valuesDict["hubitatPropertyDim"] = True
                                else:
                                    valuesDict["hubitatPropertyDim"] = False

                            elif dev.deviceTypeId == "thermostat":
                                if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                    valuesDict["hubitatPropertyValve"] = True
                                else:
                                    valuesDict["hubitatPropertyValve"] = False

                            elif dev.deviceTypeId == "valveSubModel":
                                if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                    valuesDict["hubitatPropertyValve"] = True
                                else:
                                    valuesDict["hubitatPropertyValve"] = False

                        elif hubitat_device_property == "color-name":  # TODO: Should really be checking for 'color' - awaiting fix from Kevin
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyColor"] = True
                            else:
                                valuesDict["hubitatPropertyColor"] = False

                        elif hubitat_device_property == "color-temperature":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyColorTemperature"] = True
                            else:
                                valuesDict["hubitatPropertyColorTemperature"] = False

                        elif hubitat_device_property == "contact":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyContact"] = True
                            else:
                                valuesDict["hubitatPropertyContact"] = False

                        elif hubitat_device_property == "measure-energy" or hubitat_device_property == "energy":
                            hubitat_device_property = "energy"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyEnergy"] = True
                            else:
                                valuesDict["hubitatPropertyEnergy"] = False

                        elif hubitat_device_property == "measure-humidity" or hubitat_device_property == "humidity":
                            hubitat_device_property = "humidity"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyHumidity"] = True
                            else:
                                valuesDict["hubitatPropertyHumidity"] = False

                        elif hubitat_device_property == "measure-illuminance" or hubitat_device_property == "illuminance":
                            hubitat_device_property = "illuminance"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyIlluminance"] = True
                            else:
                                valuesDict["hubitatPropertyIlluminance"] = False

                        elif hubitat_device_property == "motion":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyMotion"] = True
                            else:
                                valuesDict["hubitatPropertyMotion"] = False

                        elif hubitat_device_property == "onoff":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyOnOff"] = True
                            else:
                                valuesDict["hubitatPropertyOnOff"] = False

                        elif hubitat_device_property == "measure-power" or hubitat_device_property == "power":
                            hubitat_device_property = "power"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyPower"] = True
                            else:
                                valuesDict["hubitatPropertyPower"] = False

                        elif hubitat_device_property == "presence-sensor" or hubitat_device_property == "presence":
                            hubitat_device_property = "presence"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyPresence"] = True
                            else:
                                valuesDict["hubitatPropertyPresence"] = False

                        elif hubitat_device_property == "pressure":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyPressure"] = True
                            else:
                                valuesDict["hubitatPropertyPressure"] = False

                        elif hubitat_device_property == "measure-temperature" or hubitat_device_property == "temperature":
                            hubitat_device_property = "temperature"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyTemperature"] = True
                            else:
                                valuesDict["hubitatPropertyTemperature"] = False

                        elif hubitat_device_property == "thermostat-setpoint":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertySetpoint"] = True
                            else:
                                valuesDict["hubitatPropertySetpoint"] = False

                        elif hubitat_device_property == "measure-voltage" or hubitat_device_property == "voltage":
                            hubitat_device_property = "voltage"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyVoltage"] = True
                            else:
                                valuesDict["hubitatPropertyVoltage"] = False

                        elif hubitat_device_property == "mode":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyHvacMode"] = True
                            else:
                                valuesDict["hubitatPropertyHvacMode"] = False

                        elif hubitat_device_property == "state":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyHvacState"] = True
                            else:
                                valuesDict["hubitatPropertyHvacState"] = False

                        elif hubitat_device_property == "refresh":
                            pass  # Property not supported

                        elif hubitat_device_property == "measure-water":
                            hubitat_device_property = "water"
                            pass  # Property not supported

                        elif hubitat_device_property in "heating-setpoint,cooling-setpoint,thermostat-setpoint,mode,fanmode,state,modes,fanmodes":
                            pass  # Property not supported

                        else:
                            self.logger.warning(u"Hubitat Device '{0}' has unsupported property '{1}'".format(hubitat_device_name, hubitat_device_property))

            # Consistency checking for dimmer (color / white) - only allow color and/or white if dim is true
            if not valuesDict.get("hubitatPropertyDim", False):
                valuesDict["hubitatPropertyColor"] = False
                valuesDict["hubitatPropertyColorTemperature"] = False

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'listHubitatDeviceSelected'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

        return valuesDict

    def listHubitatDeviceProperties(self, filter="", valuesDict=None, typeId="", targetId=0):

        try:
            hubitat_device_name = valuesDict.get("hubitatDevice", "-NONE-")

            hubitat_device_properties_list = []
            if hubitat_device_name == "-SELECT-" or hubitat_device_name == "-NONE-" or hubitat_device_name == "-FIRST-":
                return hubitat_device_properties_list

            # self.logger.debug(u"List Hubitat Device Properties: {0}".format(valuesDict["hubitatHubId"]))

            hubitat_hub_dev_id = int(valuesDict.get("hubitatHubId", 0))
            if hubitat_hub_dev_id > 0 and hubitat_hub_dev_id in indigo.devices:
                hub_props = indigo.devices[hubitat_hub_dev_id].ownerProps
                hubitat_hub_name = hub_props["hub_name"]

                hubitat_device_name = valuesDict.get("hubitatDevice", "-SELECT-")
                if hubitat_device_name != "" and hubitat_device_name in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES]:
                    hubitat_device_properties = self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES].split(",")
                    for hubitat_device_property in hubitat_device_properties:
                        # if hubitat_device_property in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES:
                        #     if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                        #         if hubitat_device_property == "dim" and (typeId == "thermostat" or typeId == "valveSubModel"):
                        #             hubitat_device_property_ui = u"valve (dim)"
                        #         else:
                        #             hubitat_device_property_ui = u"{0}".format(hubitat_device_property)
                        #     else:
                        #         hubitat_device_property_ui = u"{0} [n/a]".format(hubitat_device_property)
                        #     hubitat_device_properties_list.append((hubitat_device_property, hubitat_device_property_ui))

                        hubitat_device_property_ui = u"{0}".format(hubitat_device_property)
                        if hubitat_device_property in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES[typeId]:
                            hubitat_device_property_ui = u"{0} [Primary]".format(hubitat_device_property)
                        elif hubitat_device_property == "dim" and typeId == "thermostat":
                            hubitat_device_property_ui = u"valve [dim]"
                        elif hubitat_device_property[0:8] == "measure-":
                            hubitat_device_property_ui = hubitat_device_property[8:]
                        hubitat_device_properties_list.append((hubitat_device_property, hubitat_device_property_ui))

                # Bespoke property fix(es). TODO: Remove this code once HE MQTT has been fixed
                hubitat_device_driver = valuesDict.get("hubitatDeviceDriver", "")
                if hubitat_device_driver == "Xiaomi Aqara Mijia Sensors and Switches":
                    if "pressure" not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES]:
                        hubitat_device_properties_list.append(("pressure", "pressure"))
                        self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] = u"{0},pressure"\
                            .format(self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES])

            self.logger.debug(u"Hubitat Device Properties: {0}".format(hubitat_device_properties_list))

            return sorted(hubitat_device_properties_list, key=lambda name: name[1].lower())   # sort by hubitat device property name

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'listHubitatDeviceSelected'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    def mqttListHubitatDevices(self, filter="", valuesDict=None, typeId="", targetId=0):
        try:
            hubitat_devices_list = []

            self.logger.debug(u"MQTT List Hubitat Devices [1]")

            hubitat_devices_list.append(("-SELECT-", "-- Select Hubitat Device(s) --"))

            for hubitat_hub_name in self.globals[HE_HUBS].iterkeys():
                for hubitat_device_name, hubitat_devices_details in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES].items():
                    hubitat_hub_and_device_name_key = u"{0}|||{1}".format(hubitat_hub_name, hubitat_device_name)
                    hubitat_hub_and_device_name_value = u"{0} | {1}".format(hubitat_hub_name, hubitat_device_name)
                    hubitat_devices_list.append((hubitat_hub_and_device_name_key, hubitat_hub_and_device_name_value))
            return sorted(hubitat_devices_list, key=lambda name: name[1].lower())   # sort by hubitat device name
        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'mqttListHubitatDevices'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    def refreshHubitatDevice(self, valuesDict=None, typeId="", targetId=0):
        try:
            valuesDictUpdated = self.listHubitatDeviceSelected(valuesDict, typeId, targetId)

            return valuesDictUpdated

        except StandardError as standard_error_message:
            self.logger.error(u"Error detected in 'plugin' method 'refreshHubitatDevice'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, standard_error_message))

    def process_set_color_levels(self, action, dev, hubitat_hub_name):
        try:
            self.logger.debug(u"processSetColorLevels ACTION:\n{0} ".format(action))

            dev_props = dev.pluginProps
            hubitat_device = dev_props["hubitatDevice"]

            # Determine Color / White Mode
            color_mode = False

            # First check if color is being set by the action Set RGBW levels
            if "redLevel" in action.actionValue and \
                    "greenLevel" in action.actionValue and \
                    "blueLevel" in action.actionValue:
                if float(action.actionValue["redLevel"]) > 0.0 or \
                        float(action.actionValue["greenLevel"]) > 0.0 or \
                        float(action.actionValue["blueLevel"]) > 0.0:
                    color_mode = True

            if (not color_mode) and (("whiteLevel" in action.actionValue) or ("whiteTemperature" in action.actionValue)):
                # If either of "whiteLevel" or "whiteTemperature" are altered - assume mode is White

                white_level = int(dev.states["whiteLevel"])
                white_temperature = int(dev.states["whiteTemperature"])

                if "whiteLevel" in action.actionValue:
                    white_level = int(action.actionValue["whiteLevel"])

                if "whiteTemperature" in action.actionValue:
                    white_temperature = int(action.actionValue["whiteTemperature"])
                    # if white_temperature < 2500:
                    #     white_temperature = 2500
                    # elif white_temperature > 9000:
                    #     white_temperature = 9000

                kelvin = min(ROUNDED_KELVINS, key=lambda x: abs(x - white_temperature))
                rgb, kelvin_description = ROUNDED_KELVINS[kelvin]

                topic = u"{0}/{1}/{2}/color-temperature/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-lamp_rgbw/color-temperature/set"
                topic_payload = u"{0}".format(white_temperature)
                self.publish_topic(hubitat_hub_name, topic, topic_payload)
                topic = u"{0}/{1}/{2}/dim/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-lamp_rgbw/dim/set"
                topic_payload = u"{0}".format(white_level)
                self.publish_topic(hubitat_hub_name, topic, topic_payload)
                self.logger.info(u"sent \"{0}\" set White Level to \"{1}\""
                                 u" and White Temperature to \"{2}\""
                                 .format(dev.name, int(white_level), kelvin_description))

            else:
                # As neither of "whiteTemperature" or "whiteTemperature" are set - assume mode is Colour

                props = dev.pluginProps
                if ("SupportsRGB" in props) and props["SupportsRGB"]:  # Check device supports color
                    red_level = float(dev.states["redLevel"])
                    green_level = float(dev.states["greenLevel"])
                    blue_level = float(dev.states["blueLevel"])

                    if "redLevel" in action.actionValue:
                        red_level = float(action.actionValue["redLevel"])
                    if "greenLevel" in action.actionValue:
                        green_level = float(action.actionValue["greenLevel"])
                    if "blueLevel" in action.actionValue:
                        blue_level = float(action.actionValue["blueLevel"])

                    self.logger.debug(u"sent \"{0}\" Red = {1}[{2}], Green = {3}[{4}], Blue = {5}[{6}]"
                                      .format(dev.name, red_level, int(red_level * 2.56), green_level,
                                              int(green_level * 2.56), blue_level, int(blue_level * 2.56)))

                    red = int((red_level * 256.0) / 100.0)
                    red = 255 if red > 255 else red
                    green = int((green_level * 256.0) / 100.0)
                    green = 255 if green > 255 else green
                    blue = int((blue_level * 256.0) / 100.0)
                    blue = 255 if blue > 255 else blue

                    he_rgb = "#{0:02x}{1:02x}{2:02x}".format(red, green, blue).upper()
                    # he_rgb2 = "RED:{0:02x}, GREEN:{1:02x}, BLUE:{2:02x}".format(red, green, blue).upper()

                    topic = u"{0}/{1}/{2}/color/rgb/set".format(HE_HUB_ROOT_TOPIC, hubitat_hub_name, hubitat_device)  # e.g. "homie/home-1/study-lamp_rgbw/color/rgb/set"

                    topic_payload = u"{0}".format(he_rgb)
                    self.publish_topic(hubitat_hub_name, topic, topic_payload)

                    self.logger.info(u"sent \"{0}\" RGB Levels: Red {1}%, Green {2}%, Blue {3}%"
                                     .format(dev.name, int(red_level), int(green_level), int(blue_level)))

        except StandardError, err:
            self.logger.error(u"Error detected in 'plugin' method 'processSetColorLevels'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, err))

    def process_sub_models(self, primary_dev, hubitat_hub_id):
        try:
            primary_dev_id = primary_dev.id
            Primary_dev_type_id = primary_dev.deviceTypeId

            if Primary_dev_type_id not in INDIGO_SUPPORTED_SUB_MODELS_BY_DEVICE or len(INDIGO_SUPPORTED_SUB_MODELS_BY_DEVICE[Primary_dev_type_id]) == 0:
                return

            # name = primary_dev.name  # TODO: PYCHARM DEBUG ONLY

            existing_secondary_dev_id_list = indigo.device.getGroupList(primary_dev_id)
            existing_secondary_dev_id_list.remove(primary_dev_id)  # Remove Primary device

            existing_sub_models = dict()
            for existing_sub_model_dev_id in existing_secondary_dev_id_list:
                existing_sub_models[indigo.devices[existing_sub_model_dev_id].deviceTypeId] = existing_sub_model_dev_id

            # At this point we have created a dictionary of sub-model types with their associated Indigo device Ids

            props = primary_dev.pluginProps
            hubitat_device = props["hubitatDevice"]

            for sub_model_type_id in INDIGO_SUPPORTED_SUB_MODELS_BY_DEVICE[Primary_dev_type_id]:
                # note usp prefis standas for "User Selectable Property"
                uspIndigo = INDIGO_SUB_MODEL_REQUIRED[sub_model_type_id][0]
                uspIndigo_Name = INDIGO_SUB_MODEL_REQUIRED[sub_model_type_id][1]
                if props.get(uspIndigo, INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) != INDIGO_SECONDARY_DEVICE:
                    # At this point the state associated with the property is not required in a secondary device ...
                    # ... therefore, if it exists, remove it.
                    if sub_model_type_id in existing_sub_models:
                        secondary_device_id = existing_sub_models[sub_model_type_id]

                        # TODO: DELETE / UNGROUP Logic Here (when and if available)

                        # t.b.a

                        # props_dict["member_of_device_group"] = False  # TODO: Reset to False as no longer a member of a device group

                        self.logger.warning(u"TODO: DELETE/UNGROUP Secondary Device '{0}' from Primary Device '{1}'".format(indigo.devices[secondary_device_id].name, primary_dev.name))
                        return
                else:
                    if sub_model_type_id not in existing_sub_models:

                        # Create Sub-Model

                        sub_model_name = u"{0} [{1}]".format(primary_dev.name, uspIndigo_Name)  # Create default name
                        # Check name is unique and if not, make it so
                        if sub_model_name in indigo.devices:
                            name_check_count = 1
                            while True:
                                check_name = u"{0}_{1}".format(sub_model_name, name_check_count)
                                if check_name not in indigo.devices:
                                    sub_model_name = check_name
                                    break
                                name_check_count += 1

                        required_props_list = INDIGO_SUB_MODEL_REQUIRED[sub_model_type_id][2]
                        props_dict = dict()
                        props_dict["hubitatHubId"] = hubitat_hub_id
                        props_dict["hubitatPropertiesInitialised"] = True
                        props_dict["member_of_device_group"] = True
                        props_dict["linkedIndigoDeviceId"] = primary_dev.id
                        props_dict["linkedIndigoDevice"] = primary_dev.name
                        props_dict["linkedHubitatDevice"] = hubitat_device

                        for key, value in required_props_list:
                            props_dict[key] = value

                        primary_props = primary_dev.ownerProps
                        primary_hubitat_device = primary_props["hubitatDevice"]

                        # Special Check for Humidity state which, if required, is shared with a temperature sub-model - So add NumHumidityInputs property
                        if sub_model_type_id == "temperatureSensorSubModel":
                            if primary_props.get("uspHumidityIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_SECONDARY_DEVICE_ADDITIONAL_STATE:
                                props_dict["NumHumidityInputs"] = 1

                        sub_model_device = indigo.device.create(protocol=indigo.kProtocol.Plugin,
                                                                address=primary_hubitat_device,
                                                                description="",
                                                                name=sub_model_name,
                                                                folder=primary_dev.folderId,
                                                                pluginId="com.autologplugin.indigoplugin.hubitat",
                                                                deviceTypeId=sub_model_type_id,
                                                                groupWithDevice=primary_dev_id,
                                                                props=props_dict)

                        # Manually need to set the model and subModel names (for UI only)
                        secondary_dev_id = sub_model_device.id
                        sub_model_device = indigo.devices[secondary_dev_id]  # Refresh Indigo Device to ensure groupWith Device isn't removed
                        sub_model_device.model = primary_dev.model
                        sub_model_device.subModel = uspIndigo_Name
                        sub_model_device.configured = True
                        sub_model_device.enabled = True
                        sub_model_device.replaceOnServer()

                        dev = indigo.devices[primary_dev_id]  # Refresh Indigo Device to ensure groupWith Device isn't removed

                        if dev.subModel != INDIGO_PRIMARY_DEVICE__MODEL_UI[Primary_dev_type_id]:
                            dev.subModel = INDIGO_PRIMARY_DEVICE__MODEL_UI[Primary_dev_type_id]
                            dev.replaceOnServer()

        except StandardError, err:
            self.logger.error(u"Error detected in 'plugin' method 'process_sub_models'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, err))

    def publish_topic(self, hubitat_hub_name, topic, payload):
        try:
            self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_MQTT_CLIENT].publish(topic, payload)

            log_mqtt_msg = True  # Assume MQTT message should be logged
            # Check if MQTT message filtering required
            if HE_MQTT_FILTERS in self.globals:
                if len(self.globals[HE_MQTT_FILTERS]) > 0:
                    topic_split = topic.split("/")
                    mqtt_filter_key = u"{0}|||{1}".format(topic_split[1], topic_split[2])
                    # As entries exist in the filter list, only log MQTT message in Hubitat device in the filterlist
                    if mqtt_filter_key not in self.globals[HE_MQTT_FILTERS]:
                        log_mqtt_msg = False  # As Hubitat device not in the filter list (and filter entries present) - don't log MQTT message

            if log_mqtt_msg:
                self.logger.topic(u">>> Published to '{0}': Topic='{1}', Payload='{2}'".format(hubitat_hub_name, topic, payload))

        except StandardError, err:
            self.logger.error(u"Error detected in 'plugin' method 'processSetColorLevels'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, err))
