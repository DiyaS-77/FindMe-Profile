import constants
from gi.repository import GLib
import dbus
import dbus.mainloop.glib
import dbus.service


class Application(dbus.service.Object):
    """
    Represents the GATT application root object.
    
    Registers GATT services.
    """

    PATH = '/org/bluez/example/app'

    def __init__(self, bus):
        """
        Initializes the GATT application.

        Args:
            bus: The system D-Bus connection.
        """
        self.path = self.PATH
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        """
        Returns:
            D-Bus object path of the application.
        """
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        """
        Adds a GATT service to the application.

        Args:
            service: The service object to be added.
        """
        self.services.append(service)

    @dbus.service.method('org.freedesktop.DBus.ObjectManager',
                         out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        """
        Returns:
            Dict of all managed D-Bus objects and their properties.
        """
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            for char in service.get_characteristics():
                response[char.get_path()] = char.get_properties()
        return response


class IASService(dbus.service.Object):
    """
    Immediate Alert Service (IAS) containing the Alert Level characteristic.
    """

    def __init__(self, bus, index):
        """
        Initializes the IAS service.

        Args:
            bus: The system D-Bus connection.
            index: Index used in object path.
        """
        self.path = f'/org/bluez/example/service{index}'
        self.bus = bus
        self.uuid = constants.IAS_UUID
        self.primary = True
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

        self.alert_level_char = AlertLevelCharacteristic(bus, 0, self)
        self.add_characteristic(self.alert_level_char)

    def get_path(self):
        """
        Returns:
            D-Bus object path of the service.
        """
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        """
        Returns:
            Dictionary of GATT service properties.
        """
        return {
            constants.GATT_SERVICE_IFACE: {
                'UUID': self.uuid,
                'Primary': self.primary,
                'Characteristics': dbus.Array(
                    [char.get_path() for char in self.characteristics],
                    signature='o')
            }
        }

    def add_characteristic(self, char):
        """
        Adds a characteristic to the service.

        Args:
            char: The characteristic object.
        """
        self.characteristics.append(char)

    def get_characteristics(self):
        """
        Returns:
            List of characteristics in the service.
        """
        return self.characteristics


class AlertLevelCharacteristic(dbus.service.Object):
    """
    GATT Characteristic supporting Write and Notify operations.
    
    Allows clients to write an alert level and notifies them.
    """

    def __init__(self, bus, index, service):
        """
        Initializes the Alert Level characteristic.

        Args:
            bus: The system D-Bus connection.
            index: Index used in the object path.
            service: The parent service object.
        """
        self.path = f'{service.get_path()}/char{index}'
        self.bus = bus
        self.service = service
        self.uuid = constants.ALERT_LEVEL_UUID
        self.flags = ['write-without-response', 'notify']
        self.notifying = False
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        """
        Returns:
            D-Bus object path of the characteristic.
        """
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        """
        Returns:
            Dictionary of GATT characteristic properties.
        """
        return {
            constants.GATT_CHARACTERISTIC_IFACE: {
                'UUID': self.uuid,
                'Service': self.service.get_path(),
                'Flags': dbus.Array(self.flags, signature='s'),
                'Notifying': dbus.Boolean(self.notifying)
            }
        }

    @dbus.service.method(constants.GATT_CHARACTERISTIC_IFACE,
                         in_signature='aya{sv}', out_signature='')
    def WriteValue(self, value, options):
        """
        Handles write requests from clients.

        Args:
            value: Byte array of the written value.
            options: Additional write options (unused).
        """
        if not value:
            print("[AlertLevelCharacteristic] Received empty value")
            return

        level = int(value[0])
        msg = "Unknown Alert"
        if level == 0:
            msg = "No Alert"
        elif level == 1:
            msg = "Mild Alert"
        elif level == 2:
            msg = "High Alert"

        print(f"[AlertLevelCharacteristic] Received alert level: {msg}")
        self.send_notification(msg)

    @dbus.service.method(constants.GATT_CHARACTERISTIC_IFACE,
                         in_signature='', out_signature='')
    def StartNotify(self):
        """
        Starts notifications when a client subscribes.
        """
        self.notifying = True
        print("[AlertLevelCharacteristic] Notifications enabled")

    @dbus.service.method(constants.GATT_CHARACTERISTIC_IFACE,
                         in_signature='', out_signature='')
    def StopNotify(self):
        """
        Stops notifications when a client unsubscribes.
        """
        self.notifying = False
        print("[AlertLevelCharacteristic] Notifications disabled")

    def send_notification(self, message):
        """
        Sends a notification to subscribed clients.

        Args:
            message: The alert message string to send.
        """
        if not self.notifying:
            print("[AlertLevelCharacteristic] Notification skipped (not notifying)")
            return
        value = [dbus.Byte(ord(c)) for c in message]
        self.PropertiesChanged(constants.GATT_CHARACTERISTIC_IFACE,
                               {'Value': dbus.Array(value, signature='y')}, [])

    @dbus.service.signal('org.freedesktop.DBus.Properties',
                         signature='sa{sv}as')
    def PropertiesChanged(self, interface, changed, invalidated):
        """
        Signal emitted when a property changes.

        Args:
            interface: D-Bus interface.
            changed: Changed properties.
            invalidated: Invalidated properties.
        """
        pass


class Advertisement(dbus.service.Object):
    """
    LE Advertisement for the BLE peripheral.
    """

    PATH = '/org/bluez/example/advertisement0'

    def __init__(self, bus):
        """
        Initializes the LE advertisement.

        Args:
            bus: The system D-Bus connection.
        """
        self.bus = bus
        dbus.service.Object.__init__(self, bus, self.PATH)

    @dbus.service.method('org.freedesktop.DBus.Properties',
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        """
        Returns advertisement properties.

        Args:
            interface: Requested interface.

        Returns:
            Dictionary of advertisement properties.
        """
        return {
            'Type': 'peripheral',
            'ServiceUUIDs': dbus.Array([constants.IAS_UUID], signature='s'),
            'LocalName': 'FindMeServer',
            'IncludeTxPower': dbus.Boolean(True)
        }

    @dbus.service.method(constants.LE_ADVERTISEMENT_IFACE,
                         in_signature='', out_signature='')
    def Release(self):
        """
        Called by BlueZ when the advertisement is released.
        """
        print("Advertisement released")


def find_adapter(bus):
    """
    Finds the first available Bluetooth adapter on the system.

    Args:
        bus: The system D-Bus connection.

    Returns:
        D-Bus object path of the adapter, or None if not found.
    """
    manager = dbus.Interface(bus.get_object(constants.BLUEZ_SERVICE_NAME, '/'),
                             'org.freedesktop.DBus.ObjectManager')
    objects = manager.GetManagedObjects()
    for path, interfaces in objects.items():
        if constants.ADAPTER_IFACE in interfaces:
            return path
    return None

