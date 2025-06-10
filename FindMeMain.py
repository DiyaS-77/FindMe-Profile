import dbus
import dbus.mainloop.glib
from gi.repository import GLib
from FindMeServer import (
    BLUEZ_SERVICE_NAME, ADAPTER_IFACE, GATT_MANAGER_IFACE,
    ADVERTISING_MANAGER_IFACE, Application, IASService,Advertisement, find_adapter
)

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter_path = find_adapter(bus)
    if not adapter_path:
        print(" No Bluetooth adapter found.")
        return

    adapter = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path), ADAPTER_IFACE)
    adapter_props = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path),
                                   'org.freedesktop.DBus.Properties')
    adapter_props.Set(ADAPTER_IFACE, 'Powered', dbus.Boolean(1))

    # GATT application 
    service_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path),
                                     GATT_MANAGER_IFACE)
    app = Application(bus)
    ias_service = IASService(bus, 0)
    app.add_service(ias_service)

    service_manager.RegisterApplication(app.get_path(), {},
        reply_handler=lambda: print(" GATT application registered"),
        error_handler=lambda e: print(f" Failed to register GATT application: {e}"))
   
    # BLE Advertisement

    ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path),
                                ADVERTISING_MANAGER_IFACE)
    advertisement = Advertisement(bus)
    ad_manager.RegisterAdvertisement(advertisement.PATH, {},
        reply_handler=lambda: print(" BLE advertisement registered"),
        error_handler=lambda e: print(f" Failed to register advertisement: {e}"))
    try:
        GLib.MainLoop().run()
    except KeyboardInterrupt:
        print("\nServer stopped by user")

if __name__ == '__main__':
    main()

