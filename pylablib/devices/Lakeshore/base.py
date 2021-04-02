from ...core.devio import comm_backend, SCPI, interface
from ...core.utils import funcargparse

import collections


TLakeshore218AnalogSettings=collections.namedtuple("TAnalogSettings",["bipolar","mode","channel","source","high_value","low_value","man_value"])
TLakeshore218FilterSettings=collections.namedtuple("TFilterSettings",["enabled","points","window"])
class Lakeshore218(SCPI.SCPIDevice):
    """
    Lakeshore 218 temperature controller.

    The channels are enumerated from 1 to 8 and are split into 2 groups: ``"A"`` for 1-4 and ``"B"`` for 5-8.

    Args:
        conn: serial connection parameters (usually port or a tuple containing port and baudrate)
    """
    _default_write_sync=True
    def __init__(self, conn):
        conn=comm_backend.SerialDeviceBackend.combine_conn(conn,("COM1",9600,7,'E',1))
        SCPI.SCPIDevice.__init__(self,conn,backend="serial",term_write="\r\n",term_read="\r\n")
        self._add_settings_variable("enabled",self.is_enabled,self.set_enabled,mux=(range(1,9),0))
        self._add_settings_variable("sensor_type",self.get_sensor_type,self.set_sensor_type,mux=("AB",0))
        self._add_status_variable("temperature",self.get_all_temperatures)
        self._add_status_variable("sensor_reading",self.get_all_sensor_readings,priority=-1)
        self._add_status_variable("analog_output",self.get_analog_output,mux=((1,2),))
        self._add_settings_variable("analog_output_settings",self.get_analog_output_settings,self.setup_analog_output,priority=-3,mux=((1,2),0))
        self._add_settings_variable("filter_settings",self.get_filter_settings,self.setup_filter,priority=-3,mux=(range(1,9),0))
        try:
            self.get_id(timeout=2.)
        except self.instr.Error as e:
            self.close()
            raise self.instr.BackendOpenError(e)
    _float_fmt="{:.3f}"

    _p_channel=interface.RangeParameterClass("channel",1,8)
    @interface.use_parameters
    def is_enabled(self, channel):
        """Check if a given channel is enabled"""
        return self.ask("INPUT? {}".format(channel),"bool")
    @interface.use_parameters
    def set_enabled(self, channel, enabled=True):
        """Enable or disable a given channel"""
        self.write("INPUT {} {}".format(channel, 1 if enabled else 0))
        return self.is_enabled(channel)
    
    _p_group=interface.EnumParameterClass("group",["A","B"])
    _p_sensor_type=interface.EnumParameterClass("sensor_type",{"diode_2.5":0,"diode_7.5":1,"plat_250":2,"plat_500":3,"plat_5k":4,"cernox":5})
    @interface.use_parameters
    def get_sensor_type(self, group):
        """
        Get sensort type for a given group (``"A"`` for sensors 1-4 or ``"B"`` for sensors 5-8).

        For types, see ``INTYPE`` command description in the Lakeshore 218 programming manual.
        """
        return self.ask("INTYPE? {}".format(group),"int")
    @interface.use_parameters
    def set_sensor_type(self, group, sensor_type):
        """
        Set sensort type for a given group (``"A"`` for sensors 1-4 or ``"B"`` for sensors 5-8).

        For types, see ``INTYPE`` command description in the Lakeshore 218 programming manual.
        """
        self.write("INTYPE {} {}".format(group,sensor_type))
        self.wait_dev()
        return self.get_sensor_type(group)
    
    @interface.use_parameters
    def get_temperature(self, channel):
        """Get readings (in Kelvin) on a given channel"""
        return self.ask("KRDG? {}".format(channel),"float")
    def get_all_temperatures(self):
        """Get readings (in Kelvin) on all channels"""
        data=self.ask("KRDG? 0")
        return [float(x.strip()) for x in data.split(",")]
    
    @interface.use_parameters
    def get_sensor_reading(self, channel):
        """Get readings (in sensor units) on a given channel"""
        return self.ask("SRDG? {}".format(channel),"float")
    def get_all_sensor_readings(self):
        """Get readings (in sensor units) on all channels"""
        data=self.ask("SRDG? 0")
        return [float(x.strip()) for x in data.split(",")]

    _p_output=interface.RangeParameterClass("output",1,2)
    _p_output_mode=interface.EnumParameterClass("output_mode",{"off":0,"input":1,"manual":2})
    _p_source=interface.EnumParameterClass("source",{"kelvin":1,"celsius":2,"sensor":3,"linear":4})
    @interface.use_parameters(_returns=(None,_p_output_mode,None,_p_source,None,None,None))
    def get_analog_output_settings(self, output):
        """
        Get analog output settings for a given output (1 or 2).

        For parameters, see ``ANALOG`` command description in the Lakeshore 218 programming manual.
        """
        values=self.ask("ANALOG? {}".format(output),["bool","int","int","int","float","float","float"])
        return TLakeshore218AnalogSettings(*values)
    @interface.use_parameters(mode="output_mode")
    def setup_analog_output(self, output, bipolar=None, mode=None, channel=None, source=None, high_value=None, low_value=None, man_value=None):
        """
        Setup analog output settings for a given output (1 or 2).

        For parameters, see ``ANALOG`` command description in the Lakeshore 218 programming manual.
        Value of ``None`` means keeping the current parameter value.
        """
        current=self._call_without_parameters(self.get_analog_output_settings,output)
        value=[c if v is None else v for c,v in zip(current,[bipolar,mode,channel,source,high_value,low_value,man_value])]
        self.write("ANALOG",[output]+value)
        return self.get_analog_output_settings(output)
    def set_analog_output_value(self, output, value, bipolar=False, enabled=True):
        """
        Set manual analog output value.

        A simplified version of :meth:`setup_analog_output`.
        """
        if not enabled:
            self.setup_analog_output(output,mode="off")
        else:
            self.setup_analog_output(output,bipolar=bipolar,mode="manual",man_value=value)
        return self.get_analog_output(output)
    @interface.use_parameters
    def get_analog_output(self, output):
        """Get value (in percents of the total range) at a given output (1 or 2)"""
        return self.ask("AOUT? {}".format(output),"float")

    @interface.use_parameters
    def get_filter_settings(self, channel):
        """
        Get input filter settings for a given input (1 to 8).

        For parameters, see ``FILTER`` command description in the Lakeshore 218 programming manual.
        """
        values=self.ask("FILTER? {}".format(channel),["bool","int","int"])
        return TLakeshore218FilterSettings(*values)
    def setup_filter(self, channel, enabled=None, points=None, window=None):
        """
        Setup input filter settings for a given input (1 to 8).

        For parameters, see ``FILTER`` command description in the Lakeshore 218 programming manual.
        Value of ``None`` means keeping the current parameter value.
        """
        current=self._call_without_parameters(self.get_filter_settings,channel)
        value=[c if v is None else v for c,v in zip(current,[enabled,points,window])]
        self.write("FILTER",[channel]+value)
        return self.get_filter_settings(channel)


class Lakeshore370(SCPI.SCPIDevice):
    """
    Lakeshore 370 temperature controller.

    All channels are enumerated from 0.

    Args:
        conn: serial connection parameters (usually port or a tuple containing port and baudrate)
    """
    def __init__(self, conn):
        SCPI.SCPIDevice.__init__(self,conn)
        try:
            self.get_id(timeout=2.)
        except self.instr.Error as e:
            self.close()
            raise self.instr.BackendOpenError(e)
    
    def get_resistance(self, channel):
        """Get resistance readings (in Ohm) on a given channel"""
        return self.ask("RDGR? {:2d}".format(channel),"float")
    def get_sensor_power(self, channel):
        """Get dissipated power (in W) on a given channel"""
        return self.ask("RDGPWR? {:2d}".format(channel),"float")
    
    def select_channel(self, channel):
        """Select measurement channel"""
        self.write("SCAN {:2d},0".format(channel))
    def get_channel(self):
        """Get current measurement channel"""
        return int(self.ask("SCAN?").split(",")[0].strip())
    def setup_channel(self, channel=None, mode="V", exc_range=1, res_range=22, autorange=True):
        """
        Setup a measurement channel (current channel by default).

        `mode` is the excitation mode (``"I"`` or ``"V"``), `exc_range` is the excitation range, `res_range` is the resistance range.
        For range descriptions, see Lakeshore 370 programming manual.
        """
        funcargparse.check_parameter_range(mode,"mode","IV")
        channel=0 if channel is None else channel
        mode=0 if mode=="V" else 1
        autorange=1 if autorange else 0
        self.write("RDGRNG {:2d},{},{:2d},{:2d},{},0".format(channel,mode,exc_range,res_range,autorange))
    
    def setup_heater_openloop(self, heater_range, heater_percent, heater_res=100.):
        """
        Setup a heater in the open loop mode.

        `heater_range` is the heating range, `heater_percent` is the excitation percentage within the range, `heater_res` is the heater resistance (in Ohm).
        For range descriptions, see Lakeshore 370 programming manual.
        """
        self.write("CMODE 3")
        self.write("CSET 1,0,1,25,1,{},{:f}".format(heater_range,heater_res))
        self.write("HTRRNG {}".format(heater_range))
        self.write("MOUT {:f}".format(heater_percent))
    def get_heater_settings_openloop(self):
        """
        Get heater settings in the open loop mode.

        Return tuple ``(heater_range, heater_percent, heater_res)``, where `heater_range` is the heating range,
        `heater_percent` is the excitation percentage within the range, `heater_res` is the heater resistance (in Ohm).
        For range descriptions, see Lakeshore 370 programming manual.
        """
        cset_reply=[s.strip() for s in self.ask("CSET?").split(",")]
        heater_percent=self.ask("MOUT?","float")
        heater_range=self.ask("HTRRNG?","int")
        #return int(cset_reply[5]),heater_percent,float(cset_reply[6])
        return heater_range,heater_percent,float(cset_reply[6])
    
    def set_analog_output(self, channel, value):
        """Set analog output value at a given channel"""
        if value==0:
            self.write("ANALOG {},0,0,1,1,500.,0,0.".format(channel))
        else:
            self.write("ANALOG {},0,2,1,1,500.,0,{:f}".format(channel,value))
        return self.get_analog_output(channel)
    def get_analog_output(self, channel):
        """Get analog output value at a given channel"""
        return self.ask("AOUT? {}".format(channel),"float")