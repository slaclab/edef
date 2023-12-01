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
    print('dev bsabuffer!')
    prefix = "BSA:SYS0:1"
    def __init__(self, name, user=None, number=None, avg=1, measurements=1000, destination_mode=None, destination_masks=None, avg_callback=None, measurements_callback=None, ctrl_callback=None):
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
        if number is None:
            #We only change the configuration of the edef if it is a brand new one.
            self.n_avg = avg
            self.n_measurements = measurements
            if destination_mode is not None:
                self.destination_mode = destination_mode
            if destination_masks is not None:
                self.destination_masks = destination_masks
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
        if not check_available():
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
        """The number of shots to average for each measurement.
        When setting n_avg, your value will be clipped to the upper and lower limits
        of the BSA system.
        """
        return self.destination_mode_pv.get()
    
    @destination_mode.setter
    def destination_mode(self, destmode):
        self.destination_mode_pv.put(destmode)

    @property
    def destination_masks(self):
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
                bit_mask = bit_mask | (val << bit_num)
        else:
            for mask in masks:
                bit_num = self.bit_mask_name_cache[mask]
                bit_mask = bit_mask | (1 << bit_num)
        self.destination_mask_pv.put(bit_mask)

    def clear_masks(self):
        self.destination_mask_pv.put(0)

    def populate_bit_mask_name_cache(self):
        bit_nums = list(range(0, NUM_MASK_BITS + 1))
        bit_name_pvs = ["{prefix}:{num}:DST{n}.DESC".format(prefix=self.prefix, num=self.number, n=n) for n in bit_nums]
        bit_names = epics.caget_many(bit_name_pvs)
        self.bit_mask_name_cache = {bit_name: bit_num for bit_name, bit_num in zip(bit_names, bit_nums)}
        self.bit_mask_reverse_cache = {bit_num: bit_name for bit_name, bit_num in zip(bit_names, bit_nums)}

    def start(self, callback=None):
        """Starts data acquisition. 
        This is equivalent to clicking the 'On' button on the buffer's EDM panel.
        Raises an exception if the buffer was not properly reserved.
        Returns:
            bool: True if successful, False otherwise.
        """ 
        if not self.is_reserved():
            raise Exception("BSA Buffer was not reserved, cannot acquire data.")
            return False
        if callback is not None:
            num_to_acquire = self.num_to_acquire_pv.get()
            full_done_cb = partial(self._done_callback, num_to_acquire, callback)
            self.num_acquired_pv.add_callback(full_done_cb)
        self.ctrl_pv.put(1)
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

    def _done_callback(self, num_to_acquire, user_cb, value=None, cb_info=None, **kws):
        if value != num_to_acquire:
            return
        else:
            user_cb()
            cb_info[1].remove_callback(cb_info[0])  

    def wait_for_complete(self):
        while not self.is_acquisition_complete():
            time.sleep(0.05)

    def is_acquisition_complete(self):
        """Checks if the buffer is done collecting data.
        Looks to see if the "Total Acquired so far" PV matches the "Total to Acquire" PV.
        If the two match, it is assumed that data acquisition is complete.
        Raises an exception if the buffer was not properly reserved.
        Returns:
            bool: True if acquisition is complete, False otherwise.
        """
        if not self.is_reserved():
            raise Exception("BSA Buffer was not reserved, could not acquire data.")
        num_to_acquire = self.n_measurements_pv.get()
        num_acquired = self.num_acquired_pv.get()
        return num_acquired == num_to_acquire

    def is_data_ready(self):
        """Checks if the BSA data Ready indicator is indicating Ready.
        Returns:
            bool: True if data ready indicator indicates ready, False otherwise
        """
        ready = bool(self.data_ready_pv.get())
        return ready

    def buffer_pv(self, pv, suffix='HST'):
        return "{pv}{suffix}{num}".format(pv=pv, suffix=suffix, num=self.number)

    def get_buffer(self, pv, suffix='HST'):
        string_types = (str)
        if sys.version_info[0] == 2:
            string_types = (str, unicode)
        actual_acquired = self.num_acquired()
        if actual_acquired > 0: # If 0 points, waiting for 'data ready' is pointless
            print("Checking if BSA data is ready to retrieve...")
            while not self.is_data_ready():
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
