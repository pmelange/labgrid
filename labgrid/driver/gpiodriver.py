"""All GPIO-related drivers"""
import attr
import time
import gpiod

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..resource.remote import NetworkLibGPIO, NetworkSysfsGPIO
from ..step import step
from .common import Driver
from ..util.agentwrapper import AgentWrapper


@target_factory.reg_driver
@attr.s(eq=False)
class LibGPIODigitalOutputDriver(Driver, DigitalOutputProtocol):

    bindings = {
        "gpio": {"LibGPIO", "NetworkLibGPIO"},
    }
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def on_activate(self):
        if isinstance(self.gpio, NetworkLibGPIO):
            host = self.gpio.host
        else:
            host = None

        if not gpiod.is_gpiochip_device(self.gpio.gpiochip):
            raise ValueError(f'{self.gpio.gpiochip} is not a valid gpiochip')
        try:
            self.request=gpiod.request_lines(self.gpio.gpiochip,
                                             consumer="labgrid",
                                             config={
                                                 self.gpio.line: gpiod.LineSettings(
                                                     direction=gpiod.line.Direction.AS_IS,
                                                     invert=self.gpio.invert
                                                     )
                                                 },
                                             )
        except Exception as e:
            raise type(e)(f'{self.gpio.gpiochip} {self.gpio.line}: {str(e)}')

        line_value=self.request.get_value(self.gpio.line)
        self.request.reconfigure_lines(config={
            self.gpio.line: gpiod.LineSettings(
                direction=gpiod.line.Direction.OUTPUT,
                output_value=line_value,
                invert=self.gpio.invert)})

    def on_deactivate(self):
        self.request.release()

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        self.request.set_value(self.gpio.line, gpiod.line.Value(status))

    @Driver.check_active
    @step(result=True)
    def get(self):
        return self.request.get_value(self.gpio.line)

    @Driver.check_active
    @step(result=True)
    def invert(self):
        self.set(not self.get())

@target_factory.reg_driver
@attr.s(eq=False)
class GpioDigitalOutputDriver(Driver, DigitalOutputProtocol):

    bindings = {
        "gpio": {"SysfsGPIO", "NetworkSysfsGPIO"},
    }
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        if isinstance(self.gpio, NetworkSysfsGPIO):
            host = self.gpio.host
        else:
            host = None
        self.wrapper = AgentWrapper(host)
        self.proxy = self.wrapper.load('sysfsgpio')

    def on_deactivate(self):
        self.wrapper.close()
        self.wrapper = None
        self.proxy = None

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        self.proxy.set(self.gpio.index, self.gpio.invert, status)

    @Driver.check_active
    @step(result=True)
    def get(self):
        return self.proxy.get(self.gpio.index, self.gpio.invert)

    @Driver.check_active
    @step(result=True)
    def invert(self):
        self.set(not self.get())
