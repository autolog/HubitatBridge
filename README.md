# Hubitat Bridge

Enables a two-way bridge between Indigo and a Hubitat Elevation hub device. This faciltates acess to Zigbee and additional Z-Wave devices attached to the Hubitat.

Support is also included for Tasmota plugs.


| Requirement            |                     |   |
|------------------------|---------------------|---|
| Minimum Indigo Version | 2022.1              |   |
| Python Library (API)   | Third Party         | Hubitat MQTT App by @kevin |
| Additional Python Packages | Yes             | Cryptography [See Note]|
| Requires Local Network | Yes                 |   |
| Requires Internet      | No            	   |   |
| Hardware Interface     | Yes                 | Hubitat Elevation Hub device  |

## Quick Start

1. Install Plugin
3. Create a Hubitat Bridge > MQTT Broker device to connect to MQTT
4. Create a Hubitat Bridge > Hubitat Elevation Hub device
5. Create Hubitat Bridge devices to reflect Hubitat devices published by the MQTT App on the Hubitat
6. Optionally, create a Hubitat Bridge > Indigo Export device to publish Indigo devices to Hubitat, so that they can be discovered by the MQTT App in Hubitat

Note: The plugin requires the Python Cryptography package. Enter 'pip3 install cryptography' in a terminal session to install it and then relaod the plugin.


**PluginID**: com.autologplugin.indigoplugin.lifxcontroller