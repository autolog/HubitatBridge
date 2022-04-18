#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Hubitat - Plugin © Autolog 2021-2022
#

try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

import colorsys
import logging
import queue
import sys
import threading
import traceback

from constants import *


def _no_image():
    try:
        return getattr(indigo.kStateImageSel, "NoImage")  # Python 3
    except AttributeError:
        return getattr(indigo.kStateImageSel, "None")  # Python 2


# noinspection PyPep8Naming
class ThreadExportHandler(threading.Thread):

    # This class handles Hubitat Hub processing

    def __init__(self, pluginGlobals, event):
        try:

            threading.Thread.__init__(self)

            self.globals = pluginGlobals

            self.exportHandlerLogger = logging.getLogger("Plugin.HE_HUB")

            self.threadStop = event

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]  # noqa [Ignore duplicate code warning]
        module = filename.split('/')
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method}'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.exportHandlerLogger.error(log_message)

    def run(self):
        try:
            while not self.threadStop.is_set():
                try:
                    mqtt_message_sequence, mqtt_process_command, mqtt_topics, mqtt_topics_list, mqtt_payload = self.globals[QUEUES][MQTT_EXPORT_QUEUE].get(True, 5)

                    if mqtt_process_command == MQTT_PROCESS_COMMAND_HANDLE_TOPICS:
                        self.handle_topics(mqtt_topics, mqtt_topics_list, mqtt_payload)

                except queue.Empty:
                    pass
                except Exception as exception_error:
                    self.exception_handler(exception_error, True)  # Log error and display failing statement
            else:
                if not self.globals[EXPORT][EXPORT_NAME] is None:

                    pass
                    # TODO: At this point, queue a recovery for n seconds time
                    # TODO: In the meanwhile, just disable and then enable the Indigo Hubitat Elevation Hub device

            self.exportHandlerLogger.debug("Hub Handler Thread close-down commencing.")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def handle_topics(self, topics_unsplit, topics_list, payload):  # noqa
        # Note that there are a minimum of three topic entries in the topics_list
        try:
            if len(topics_list) != 5:
                return

            if topics_list[4] != "set":
                return

            # self.exportHandlerLogger.error(f">>> Received Export /Set: Topic='{topics_unsplit}', Pay#load='{payload}'")  # noqa [unresolved attribute reference]  # TODO: TESTING ONLY

            subscribed = False
            for mqtt_client_device_id in self.globals[EXPORT][MQTT_BROKERS]:
                if self.globals[MQTT][mqtt_client_device_id][MQTT_CONNECTED]:
                    if self.globals[MQTT][mqtt_client_device_id][MQTT_SUBSCRIBE_TO_HOMIE]:
                        subscribed = True

            if not subscribed:
                return

            # hub_dev = indigo.devices[hub_id]
            # if hub_dev.states["status"] == "Disconnected":
            #     hub_dev.updateStateOnServer(key="status", value="Connected")
            #     hub_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

            # Determinee Indigo device
            topic_id = topics_list[2]  # e.g. dev-12345678
            if topic_id[0:4] != "dev-":
                return
            dev_id = int(topic_id[4:])  # e.g. 12345678

            if dev_id not in self.globals[EXPORT][ENABLED]:
                return

            dev = indigo.devices[dev_id]

            # self.log_export_topic(topic_id, dev.name, topics_unsplit, payload)

            if topics_list[3] == "onoff":
                onoffState_is_on = True if payload == "true" else False

                if dev.onState != onoffState_is_on:
                    self.log_export_topic(topic_id, dev.name, topics_unsplit, payload, EXPORT_TOPIC_PROCESSED)
                    if onoffState_is_on:
                        indigo.device.turnOn(dev_id)
                    else:
                        indigo.device.turnOff(dev_id)
                else:
                    self.log_export_topic(topic_id, dev.name, topics_unsplit, payload, EXPORT_TOPIC_IGNORED)

            elif topics_list[3] == "dim":
                try:
                    brightness_level = int(payload)
                except ValueError:
                    self.log_export_topic(topic_id, dev.name, topics_unsplit, payload, EXPORT_TOPIC_PAYLOAD_ERROR)
                    return
                if dev.brightness != brightness_level:
                    self.log_export_topic(topic_id, dev.name, topics_unsplit, payload, EXPORT_TOPIC_PROCESSED)
                    indigo.dimmer.setBrightness(dev_id, value=brightness_level)
                else:
                    self.log_export_topic(topic_id, dev.name, topics_unsplit, payload, EXPORT_TOPIC_IGNORED)

            elif topics_list[3] == "color-mode":
                self.globals[EXPORT][ENABLED][dev.id][STORED_COLOR_MODE] = payload
                self.log_export_topic(topic_id, dev.name, topics_unsplit, payload, EXPORT_TOPIC_PROCESSED)

            elif topics_list[3] == "color-temperature":
                self.globals[EXPORT][ENABLED][dev.id][STORED_COLOR_MODE] = "CT"
                kelvin = int(payload)
                indigo.dimmer.setColorLevels(dev, whiteTemperature=kelvin)
                self.log_export_topic(topic_id, dev.name, topics_unsplit, payload, EXPORT_TOPIC_PROCESSED)

            elif topics_list[3] == "color":
                self.globals[EXPORT][ENABLED][dev.id][STORED_COLOR_MODE] = "HSV"
                # # Assume HSV
                # color_mode = "HSV"
                # if dev.id in self.globals[EXPORT][ENABLED]:
                #     if STORED_COLOR_MODE in self.globals[EXPORT][ENABLED][dev.id]:
                #         color_mode = self.globals[EXPORT][ENABLED][dev.id][STORED_COLOR_MODE]
                # if color_mode == "HSV":

                # Change HSV value to RGB
                hue, saturation, value = payload.split(",")
                try:
                    hue = float(hue) / 360.0
                    saturation = float(saturation) / 100.0
                    value = float(value) / 100.0
                    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
                    red = int(red * 100.0)
                    green = int(green * 100.0)
                    blue = int(blue * 100.0)
                    indigo.dimmer.setColorLevels(dev, redLevel=red, greenLevel=green, blueLevel=blue)
                except Exception:
                    self.log_export_topic(topic_id, dev.name, topics_unsplit, payload, EXPORT_TOPIC_PAYLOAD_ERROR)
                    return

                self.log_export_topic(topic_id, dev.name, topics_unsplit, payload, EXPORT_TOPIC_PROCESSED)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def log_export_topic(self, device_key, device_name, topic, payload, logging_type):
        try:
            if logging_type == EXPORT_TOPIC_PAYLOAD_ERROR:
                self.exportHandlerLogger.error(f">>> Received Indigo Exported: Topic='{topic}', INVALID PAYLOAD='{payload}' for '{device_name}'")  # noqa [unresolved attribute reference]
                return

            log_mqtt_msg = False  # Assume MQTT message should NOT be logged
            # Check if MQTT message filtering required
            if EXPORT_FILTERS in self.globals:
                if len(self.globals[EXPORT_FILTERS]) > 0:
                    if len(self.globals[EXPORT_FILTERS]) == 1:
                        if self.globals[EXPORT_FILTERS][0] == "dev-none":
                            return
                        elif  self.globals[EXPORT_FILTERS][0] == "dev-all":
                            log_mqtt_msg = True
                    else:
                        # As entries exist in the filter list, only log an MQTT message in Export device in the filter list
                        if device_key in self.globals[EXPORT_FILTERS]:
                            log_mqtt_msg = True

            if log_mqtt_msg:
                if logging_type == EXPORT_TOPIC_PROCESSED:
                    self.exportHandlerLogger.topic(f">>> Received Indigo Exported: Topic='{topic}', Payload='{payload}' for '{device_name}'")  # noqa [unresolved attribute reference]
                else:
                    # Assume EXPORT_TOPIC_IGNORED
                    self.exportHandlerLogger.warning(f">>> Ignoring Received Indigo Exported: Topic='{topic}', Payload='{payload}' for '{device_name}'")  # noqa [unresolved attribute reference]

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement
