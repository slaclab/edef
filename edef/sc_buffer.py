"""sc_buffer.py - A python module to interact with the SC Linac BSA Buffer system.
Author: Matt Gibbs (mgibbs@slac.stanford.edu)
"""

import sys
import epics
import os
import time
from functools import partial
from contextlib import contextmanager

NUM_MASK_BITS = 9

"""BSABuffer is a class that represents a BSA Buffer.
Instantiate a BSABuffer object to reserve one of the buffers.  Configure it,
then start data aquisition with the 'start' method."""
class BSABuffer(object):
    prefix = "BSA:SYS0:1"
    def __init__(self, name, user=None, number=None, avg=1, measurements=1000, destination_mode=None, destination_masks=None, avg_callback=None, measurements_callback=None, ctrl_callback=None, rate_mode=None, fixed_rate=None, ac_rate=None, timeslots=None):
        if number is None:
            self.number = self.reserve(name, user=user)
        else:
            self.number = number
        self.sys = "SYS0"
        self.n_avg_pv = epics.PV("{prefix}:{num}:AVGCNT".format(prefix=self.prefix, num=self.number))
        self.n_measurements_pv = epics.PV("{prefix}:{num}:MEASCNT".format(prefix=self.prefix, num=self.number))
        self.ctrl_pv = epics.PV("{prefix}:{num}:CTRL".format(prefix=self.prefix, num=self.number))
        self.num_acquired_pv = epics.PV("{prefix}:{num}:CNT".format(prefix=self.prefix, num=self.number))
        self.rate_mode_pv = epics.PV("{prefix}:{num}:RATEMODE".format(prefix=self.prefix, num=self.number))
        self.destination_mode_pv = epics.PV("{prefix}:{num}:DESTMODE".format(prefix=self.prefix, num=self.number))
        self.destination_mask_pv = epics.PV("{prefix}:{num}:DESTMASK".format(prefix=self.prefix, num=self.number))
        self.fixed_rate_pv = epics.PV("{prefix}:{num}:FIXEDRATE".format(prefix=self.prefix, num=self.number))
        self.ac_rate_pv = epics.PV("{prefix}:{num}:ACRATE".format(prefix=self.prefix, num=self.number))
        self.timeslot_mask_pv = epics.PV("{prefix}:{num}:TSLOTMASK".format(prefix=self.prefix, num=self.number))
        self.measurement_severity_pv = epics.PV("{prefix}:{num}:MEASSEVR".format(prefix=self.prefix, num=self.number))
        self.data_ready_pv = epics.PV("{prefix}:{num}:HST_READY".format(prefix=self.prefix, num=self.number))
        self.bit_mask_name_cache = {}
        self.bit_mask_reverse_cache = {}
        self.acquisition_complete = False
        if number is None:
            #We only change the configuration of the edef if it is a brand new one.
            self.n_avg = avg
            self.n_measurements = measurements
            if destination_mode is not None:
                self.destination_mode = destination_mode
            if destination_masks is not None:
                self.destination_masks = destination_masks
            if rate_mode is not None:
                self.rate_mode = rate_mode
            if fixed_rate is not None:
                self.fixed_rate = fixed_rate
            if ac_rate is not None:
                self.ac_rate = ac_rate
            if timeslots is not None:
                self.timeslots = timeslots
        # Now that we've set initial values for PVs, we can install callbacks.
        self._avg_callback = None
        self._avg_callback_index = None
        if avg_callback is not None:
            self.avg_callback = avg_callback
        self._measurements_callback = None
        self._measurements_callback_index = None
        if measurements_callback is not None:
            self.measurements_callback = measurements_callback
        self._ctrl_callback = None
        self._ctrl_callback_index = None
        if ctrl_callback is not None:
            self.ctrl_callback = ctrl_callback

    @classmethod
    def num_buffers_available(cls):
        return epics.caget("{prefix}:NFREEBSA".format(prefix=cls.prefix))
    
    @classmethod
    def check_available(cls):
        return cls.num_buffers_available() > 0

    def reserve(self, name, user=None):
        if not self.check_available():
            raise Exception("No BSA buffers available.")
        epics.caput("{prefix}:BSANAME".format(prefix=self.prefix), name, wait=True)
        timeout = 5.0
        time_elapsed = 0.0
        while time_elapsed < timeout:
            for num in range(21, 50):
                buffer_name = epics.caget("{prefix}:{num}:NAME".format(prefix=self.prefix, sys=sys, num=num))
                if buffer_name == name:
                    if user is not None:
                        epics.caput("{prefix}:{num}:USERNAME".format(prefix=self.prefix, sys=sys, num=num), str(user))
                    return num
            time.sleep(0.05)
            time_elapsed += 0.05
        #If you get this far, the edef wasn't reserved.
        #Check again if there just aren't any EDEFs.
        if not self.check_available():
            raise Exception("No BSA buffers available.")
        else:
            raise Exception("Could not reserve a BSA buffer.")
    
    def is_reserved(self):
        """Checks if the buffer has been reserved.

        This method checks if the buffer has a valid edef_num (set during initialization).
        The most common reason a buffer would not have a valid edef_num is failure to
        reserve a buffer.

        Returns:
            bool: True if the buffer is reserved, false otherwise.
        """
        if self.number is not None and self.number != 0:
            return True
        else:
            return False

    @property
    def ctrl_callback(self):
        """A method to be called when the buffer's ctrl state (whether or not the buffer is 'on') changes.
        
        The method must take one argument: the new value of the CTRL state.
        
        To remove the callback, set ctrl_callback to None.
        """
        return self._ctrl_callback

    @ctrl_callback.setter
    def ctrl_callback(self, new_callback):
        if new_callback == self._ctrl_callback:
            return
        if self._ctrl_callback is not None:
            self.ctrl_pv.remove_callback(self._ctrl_callback_index)
        self._ctrl_callback = new_callback
        if new_callback is not None:
            full_cb = partial(self._ctrl_callback_full, new_callback)
            self._ctrl_callback_index = self.ctrl_pv.add_callback(full_cb)
    
    def _ctrl_callback_full(self, user_cb, value=None, **kw):
        user_cb(value)
    
    @property
    def n_avg(self):
        """The number of shots to average for each measurement.
        When setting n_avg, your value will be clipped to the upper and lower limits
        of the BSA system.
        """
        return self.n_avg_pv.get()
    
    @n_avg.setter
    def n_avg(self, navg):
        lopr = self.n_avg_pv.get_ctrlvars()['lower_ctrl_limit']
        hopr = self.n_avg_pv.get_ctrlvars()['upper_ctrl_limit']
        self.n_avg_pv.put(min(hopr, max(lopr, navg)))

    @property
    def avg_callback(self):
        """A method to be called when the number of averages changes.
        This callback will fire whenever the buffer's AVGCNT PV changes,
        even if it happens outside this module.

        The method must take one argument: the number of averages.
        
        To remove the callback, set avg_callback to None.
        """
        return self._avg_callback

    @avg_callback.setter
    def avg_callback(self, new_callback):
        if new_callback == self._avg_callback:
            return
        if self._avg_callback is not None:
            self.n_avg_pv.remove_callback(self._avg_callback_index)
        self._avg_callback = new_callback
        if new_callback is not None:
            full_cb = partial(self._avg_callback_full, new_callback)
            self._avg_callback_index = self.n_avg_pv.add_callback(full_cb)
    
    def _avg_callback_full(self, user_cb, value=None, **kw):
        user_cb(value)
    
    @property
    def n_measurements(self):
        """The number of measurements to take.
        When setting n_measurements, your value will be clipped to the upper and lower limits
        of the BSA system.
        """
        return self.n_measurements_pv.get()

    @n_measurements.setter
    def n_measurements(self, measurements):
        lopr = self.n_measurements_pv.get_ctrlvars()['lower_ctrl_limit']
        hopr = self.n_measurements_pv.get_ctrlvars()['upper_ctrl_limit']
        self.n_measurements_pv.put(min(hopr, max(lopr, measurements)))
        
    @property
    def measurements_callback(self):
        """A method to be called when the number of measurements changes.
        This callback will fire whenever the buffer's MEASCNT PV changes,
        even if it happens outside this module.

        The method must take one argument: the number of measurements.
        
        To remove the callback, set measurements_callback to None.
        """
        return self._measurements_callback

    @measurements_callback.setter
    def measurements_callback(self, new_callback):
        if new_callback == self._measurements_callback:
            return
        if self._measurements_callback is not None:
            self.n_measurements_pv.remove_callback(self._measurements_callback_index)
        self._measurements_callback = new_callback
        if new_callback is not None:
            full_cb = partial(self._measurements_callback_full, new_callback)
            self._measurements_callback_index = self.n_measurements_pv.add_callback(full_cb)
    
    def _measurements_callback_full(self, user_cb, value=None, **kw):
        user_cb(value)
    
    @property
    def destination_mode(self):
        """
        Determines whether destination masks are used to include pulses ('Inclusion'), exclude pulses ('Exclusion'),
        or are ignored ('Disable').
        """
        return self.destination_mode_pv.get()
    
    @destination_mode.setter
    def destination_mode(self, destmode):
        self.destination_mode_pv.put(destmode)

    @property
    def destination_masks(self):
        """
        A list of destination masks used to filter pulses.
        Works in combination with destination_mode.  For a list of 
        masks, please see the BSA Buffer PyDM panel.
        
        For example, you could set this to ['SC_BSYD', 'SC_SXR'] to select
        pulses marked with SC_BSYD or SC_SXR as the destination.
        """
        if len(self.bit_mask_reverse_cache) == 0:
            self.populate_bit_mask_name_cache()
        masks = []
        bit_mask = int(self.destination_mask_pv.get())
        #Turn the combined bit mask into a list of modifier bit names
        for bit_num in self.bit_mask_reverse_cache:
            bit_val = bit_mask & (1 << bit_num)
            if bit_val != 0:
                masks.append(self.bit_mask_reverse_cache[bit_num])
        return masks

    @destination_masks.setter
    def destination_masks(self, masks):
        self.clear_masks()
        if len(self.bit_mask_name_cache) == 0:
            self.populate_bit_mask_name_cache()
        bit_mask = 0
        if isinstance(masks, dict):
            for mask, val in masks.iteritems():
                bit_num = self.bit_mask_name_cache[mask]
                destination_selection_pv = "{prefix}:{num}:DST{n}".format(prefix=self.prefix, num=self.number, n=bit_num)
                epics.caput(destination_selection_pv, 1)
                bit_mask = bit_mask | (val << bit_num)
        else:
            for mask in masks:
                bit_num = self.bit_mask_name_cache[mask]
                destination_selection_pv = "{prefix}:{num}:DST{n}".format(prefix=self.prefix, num=self.number, n=bit_num)
                epics.caput(destination_selection_pv, 1)
                bit_mask = bit_mask | (1 << bit_num)
        self.destination_mask_pv.put(bit_mask)

    def clear_masks(self):
        self.destination_mask_pv.put(0)
        for i in range(0, 6):
            destination_selection_pv = "{prefix}:{num}:DST{n}".format(prefix=self.prefix, num=self.number, n=i)
            epics.caput(destination_selection_pv, 0)

    def populate_bit_mask_name_cache(self):
        bit_nums = list(range(0, NUM_MASK_BITS + 1))
        bit_name_pvs = ["{prefix}:{num}:DST{n}.DESC".format(prefix=self.prefix, num=self.number, n=n) for n in bit_nums]
        bit_names = epics.caget_many(bit_name_pvs)
        self.bit_mask_name_cache = {bit_name: bit_num for bit_name, bit_num in zip(bit_names, bit_nums)}
        self.bit_mask_reverse_cache = {bit_num: bit_name for bit_name, bit_num in zip(bit_names, bit_nums)}

    @property
    def rate_mode(self):
        """
        Determines which rate mode ("Fixed Rate", "AC Rate", or "Exp Seq") is
        used when setting a rate filter.
        """
        return self.rate_mode_pv.get()
        
    @rate_mode.setter
    def rate_mode(self, mode):
        self.rate_mode_pv.put(mode)

    @property
    def fixed_rate(self):
        """
        Sets the fixed rate to filter to.
        Only has an effect if rate_mode is set to "Fixed Rate".
        
        For a list of available fixed rates, please see the BSA Buffer PyDM screen (expert tab).
        You must supply the rate string (including 'Hz'), integers won't work here.
        """
        return self.fixed_rate_pv.get()
    
    @fixed_rate.setter
    def fixed_rate(self, rate):
        self.fixed_rate_pv.put(rate)

    @property
    def ac_rate(self):
        """
        This sets the AC rate to filter to.
        Only has an effect if rate_mode is set to "AC Rate".
        
        For a list of available AC rates, please see the BSA Buffer PyDM screen (expert tab).
        """
        return self.ac_rate_pv.get()
    
    @ac_rate.setter
    def ac_rate(self, rate):
        self.ac_rate_pv.put(rate)
    
    @property
    def timeslots(self):
        """
        This sets the timeslots used to filter pulses.
        Only has an effect if rate_mode is set to "AC Rate".
        
        You can supply an integer (1 through 6), or a list of integers (like [1, 4]).
        When getting the value, will always return a list, even if only one timeslot is active.
        """
        bitmask = self.timeslot_mask_pv.get()
        active_timeslots = []
        for ts in range(1,7):
            if bitmask & (1 << (ts - 1)) > 1:
                active_timeslots.append(ts)
    
    @timeslots.setter
    def timeslots(self, ts_list):
        if isinstance(ts_list, int):
            ts_list = [ts_list]
        for ts in range(1,7):
            active = 1 if ts in ts_list else 0
            epics.caput(f"{self.prefix}:{self.num}:TS{ts}", active)
    
    def start(self, callback=None):
        """Starts data acquisition. 
        This is equivalent to clicking the 'On' button on the buffer's EDM panel.
        Raises an exception if the buffer was not properly reserved.
        Returns:
            bool: True if successful, False otherwise.
        """ 
        
        self.acquisition_complete = False
        
        if not self.is_reserved():
            raise Exception("BSA Buffer was not reserved, cannot acquire data.")
            return False
        if callback is not None:
            full_done_cb = partial(self._done_callback, callback)
            self.num_acquired_pv.add_callback(full_done_cb)
        self.ctrl_pv.put(1)
        
        time_out=1
        start=time.time()
        while self.is_acquisition_complete():#make sure the data ready flag switches before proceeding
            time.sleep(.01)#wait a small ammount of time
            if time.time() - start >= time_out:# time out after a while
                raise Exception("BSA Buffer was not able to start, cannot acquire data.")
                return False
        return True

    def stop(self):
        """Starts data acquisition. 
        This is equivalent to clicking the 'On' button on the buffer's PyDM panel.
        Raises an exception if the buffer was not properly reserved.
        Returns:
            bool: True if successful, False otherwise.  
        """ 
        if not self.is_reserved():
            raise Exception("BSA Buffer was not reserved, cannot stop acquisition.")
            return False
        self.ctrl_pv.put(0)
        return True

    def _done_callback(self, user_cb, value=None, cb_info=None, **kws):
        user_cb()
        cb_info[1].remove_callback(cb_info[0])  

    def wait_for_complete(self):
        while not self.is_acquisition_complete():
            time.sleep(0.05)

    def is_acquisition_complete(self):
        """Checks if the buffer is done collecting data.
        Raises an exception if the buffer was not properly reserved.
        Returns:
            bool: True if acquisition is complete, False otherwise.
        """
        
        if not self.is_reserved():
            raise Exception("BSA Buffer was not reserved, could not acquire data.")
        return bool(self.data_ready_pv.get())

    def buffer_pv(self, pv, suffix='HST'):
        return "{pv}{suffix}{num}".format(pv=pv, suffix=suffix, num=self.number)

    def get_buffer(self, pv, suffix='HST'):
        string_types = (str)
        if sys.version_info[0] == 2:
            string_types = (str, unicode)
        actual_acquired = self.num_acquired()
        if actual_acquired > 0: # If 0 points, waiting for 'data ready' is pointless
            print("Checking if BSA data is ready to retrieve...")
            while not self.is_acquisition_complete():
                time.sleep(0.05)
            print("BSA Data ready for retrieval")
        if isinstance(pv, string_types):  # Single PV
            buff = epics.caget(self.buffer_pv(pv=pv, suffix=suffix))
            #If this isn't a rolling buffer, trim it to only include the collected data.
            buff = buff[0:actual_acquired]
            return buff
        else:  # Multiple PVs
            pv_list = [self.buffer_pv(pv=a_pv, suffix=suffix) for a_pv in pv]
            suffix_length = len(suffix + str(self.number))
            buff_list = epics.caget_many(pv_list)
            buff_dict = dict(zip(pv_list, buff_list))
            buff_dict = {a_pv[:-suffix_length]: buff_dict[a_pv][0:actual_acquired] for a_pv in buff_dict}
            return buff_dict

    def get_data_buffer(self, pv):
        """Gets the collected data for an BSA measurement.
        
        Args:
            pv (str): A BSA-capable PV (for example, "GDET:FEE:241:ENRC").  All BSA
                  system suffixes, like "HSTBR" should be left off.
        Returns:
            numpy.ndarray: An array containing the collected data for the pv.
        """
        return self.get_buffer(pv, suffix='HST')

    def get_rms_buffer(self, pv):
        """Gets the RMS data buffer for an BSA measurement (or the current value of the
        buffer if n_measurements == -1).

        The RMS data buffer will only be populated if the buffer's number of pulses to 
        average per measurement (n_avg) is greater than 1.
        
        Args:
            pv (str): A BSA-capable PV (for example, "GDET:FEE:241:ENRC").  All BSA
                  system suffixes, like "HSTBR" should be left off.
        Returns:
            numpy.ndarray: An array containing the RMS data for the pv.
        """
        return self.get_buffer(pv, suffix='RMSHST')

    def get_pulse_ids(self):
        raise NotImplementedError
        #return self.get_buffer("PATT:{sys}:1:PULSEID".format(prefix=self.prefix), suffix='HST')

    def get(self, pv):
        """Gets the current value of a PV using this buffer.

        This is a convenience method equivalent to doing 
        epics.caget("GDET:FEE1:241:ENRC{num}") where {num} is the buffer's number.
        
        Args:
            pv (str): A BSA-capable PV (for example, "GDET:FEE1:241:ENRC").  All BSA
                  system suffixes, like "HSTBR" should be left off.
        Returns:
            The latest value of the pv.
        """
        string_types = (str)
        if sys.version_info[0] == 2:
            string_types = (str, unicode)
        if isinstance(pv, string_types):
            return epics.caget("{pv}{num}".format(pv=pv, num=self.number))
        else:
            pv_list = ["{a_pv}{num}".format(a_pv=a_pv, num=self.number) for a_pv in pv]
            value_list = epics.caget_many(pv_list)
            values = dict(zip(pv_list, value_list))
            return {a_pv[:-len(str(self.number))]: values[a_pv] for a_pv in values}

    def num_acquired(self):
        """Gets the number of measurements acquired by the buffer.

        This can tell you the progress of a long measurement if used while acquisition
        is in progress, or it can tell you the total number of measurements performed if the
        acquisition is complete.

        Returns:
            int: The number of pulses acquired by the buffer.
        """
        return self.num_acquired_pv.get()

    def num_to_acquire(self):
        """Gets the number of measurements to acquire by the buffer.

        Returns:
            int: The number of pulses to acquire by the buffer.
        """
        return self.n_measurements_pv.get()
        
    def release(self):
        """Releases the buffer.
        If the buffer was not properly reserved, this method will raise an exception.
        """
        if not self.is_reserved():
            raise Exception("Buffer was not reserved, cannot release.")
        epics.caput("{prefix}:{num}:FREE".format(prefix=self.prefix, num=self.number), 1)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
