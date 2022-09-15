import unittest
import edef
import os
import epics
import time
from random import randint

class EdefReservationTest(unittest.TestCase):
    def setUp(self):
        self.sys = "SYS0"
        self.initial_edefs_available = epics.caget("BSA:SYS0:1:NFREEBSA")
        self.name = "sc_buffer.py unit tests {}".format(randint(0,255))
        self.edef = edef.BSABuffer(self.name, os.uname()[1])

    def test_available_count_drops(self):
        edefs_available_after_setup = epics.caget("BSA:SYS0:1:NFREEBSA")
        self.assertTrue(edefs_available_after_setup < self.initial_edefs_available)
    
    def test_edef_name_is_correct(self):
        name_pv = "BSA:{sys}:1:{num}:NAME".format(sys=self.edef.sys, num=self.edef.number)
        fetched_name = epics.caget(name_pv)
        self.assertEqual(self.name, fetched_name)

    def tearDown(self):
        #Always try to release the event definition at the end of the test.
        try:
            self.edef.release()
        except:
            pass

class ExistingEdefTest(unittest.TestCase):
    def setUp(self):
        #Reserve an edef manually
        self.sys = "SYS0"
        self.name = "sc_buffer.py unit tests {}".format(randint(0,255))
        epics.caput("BSA:SYS0:1:BSANAME", self.name)
        time.sleep(1.0)
        #Find the number of the edef we just reserved
        self.edef_num = None
        for i in range(21,65):
            name = epics.caget("BSA:{sys}:1:{num}:NAME".format(sys=self.sys, num=i))
            if name == self.name:
                self.edef_num = i
                time.sleep(1.0) #Give the edef a bit of time to initialize.
                break
        if self.edef_num is None:
            raise RuntimeError('Manual buffer reservation failed, cannot proceed with test.')
    
    def test_existing_configuration_not_overwritten(self):
        if self.edef_num is None:
            raise RuntimeError('Manual buffer reservation failed, cannot proceed with test.')
        num_avg = 13
        epics.caput("BSA:{sys}:1:{num}:AVGCNT".format(sys=self.sys, num=self.edef_num), num_avg)
        num_meas = 20
        epics.caput("BSA:{sys}:1:{num}:MEASCNT".format(sys=self.sys, num=self.edef_num), num_meas)
        time.sleep(1.0)
        edef_obj = edef.BSABuffer("should ignore", number=self.edef_num, avg=1, measurements=1)
        time.sleep(1.0)
        self.assertEqual(edef_obj.n_avg, num_avg)
        self.assertEqual(edef_obj.n_measurements, num_meas)
        current_name = epics.caget("BSA:{sys}:1:{num}:NAME".format(sys=self.sys, num=self.edef_num))
        self.assertEqual(current_name, self.name)
        
    def tearDown(self):
        #Manually release the edef we reserved in setup.
        if self.edef_num is not None:
            epics.caput("BSA:{sys}:1:{num}:FREE".format(sys=self.sys, num=self.edef_num), 1)

class EdefReleaseTest(unittest.TestCase):
    def setUp(self):
        self.edef = edef.BSABuffer("sc_buffer.py unit tests " + str(randint(0,255)), os.uname()[1])
    
    def test_release(self):
        edefs_available_before_release = epics.caget("BSA:SYS0:1:NFREEBSA")
        if not self.edef.is_reserved():
            raise RuntimeError('BSABuffer could not be reserved, cannot proceed with test.')

        self.edef.release()
        time.sleep(1.0)
        edefs_available_after_release = epics.caget("BSA:SYS0:1:NFREEBSA")
        self.assertEqual(edefs_available_before_release, edefs_available_after_release - 1)

    def tearDown(self):
        try: 
            self.edef.release()
        except Exception as e:
            print("Exception encountered while releasing edef: {e}".format(e))

class EdefPropertiesTest(unittest.TestCase):
    def setUp(self):
        self.edef = edef.BSABuffer("sc_buffer.py unit tests " + str(randint(0,255)), os.uname()[1])
    
    def test_n_avg(self):
        n_avg = 5
        self.edef.n_avg = n_avg
        time.sleep(1.0)
        self.assertEqual(epics.caget("BSA:{sys}:1:{num}:AVGCNT".format(sys=self.edef.sys, num=self.edef.number)), n_avg)
        self.assertEqual(self.edef.n_avg, n_avg)
    
    def test_n_measurements(self):
        n_measurements = 10
        self.edef.n_measurements = n_measurements
        time.sleep(1.0)
        self.assertEqual(epics.caget("BSA:{sys}:1:{num}:MEASCNT".format(sys=self.edef.sys, num=self.edef.number)), n_measurements)
        self.assertEqual(self.edef.n_measurements, n_measurements)

    def test_destination_masks(self):
        return #Bug in BSA prevents us from properly testing this right now.
        self.assertTrue(self.edef.is_reserved())
        mask_1 = epics.caget("BSA:{sys}:1:{num}:DST0.DESC".format(sys=self.edef.sys, num=self.edef.number))
        mask_2 = epics.caget("BSA:{sys}:1:{num}:DST1.DESC".format(sys=self.edef.sys, num=self.edef.number))
        masks = [mask_1, mask_2]
        self.edef.destination_masks = masks
        time.sleep(1.0)
        read_mask_1 = epics.caget("BSA:{sys}:1:{num}:DST0".format(sys=self.edef.sys, num=self.edef.number))
        read_mask_2 = epics.caget("BSA:{sys}:1:{num}:DST1".format(sys=self.edef.sys, num=self.edef.number))
        self.assertEqual(read_mask_1, 1)
        self.assertEqual(read_mask_2, 1)

    def tearDown(self):
        try:
            self.edef.release()
        except:
            print("Exception encountered while releasing edef: {e}".format(e))


class AcquisitionTest(unittest.TestCase):
    def setUp(self):
        self.num_meas = randint(0,1000)
        self.edef = edef.BSABuffer("sc_buffer.py unit tests " + str(randint(0,255)), user=os.uname()[1], avg=1, measurements=self.num_meas)
        self.pv_list = ["BPMS:GUNB:314:X", "BPMS:HTR:120:X"]

    def test_single_acquisition(self):
        if self.edef.sys != "SYS0":
            print("Acquisition test only works on the LCLS network right now, skipping.")
            return
        self.edef.start()
        time.sleep(1.0)
        timeout = 25.0
        time_elapsed = 0.0
        while not self.edef.is_acquisition_complete():
            time_elapsed += 0.01
            if time_elapsed > timeout:
                raise RuntimeError("Timeout expired while acquiring edef data.")
            time.sleep(0.01)
        data = self.edef.get_buffer(self.pv_list[0])
        self.assertEqual(len(data), self.num_meas)

    def test_multi_acquisition(self):
        if self.edef.sys != "SYS0":
            print("Acquisition test only works on the LCLS network right now, skipping.")
            return
        self.edef.start()
        time.sleep(1.0)
        timeout = 25.0
        time_elapsed = 0.0
        while not self.edef.is_acquisition_complete():
            time_elapsed += 0.01
            if time_elapsed > timeout:
                raise RuntimeError("Timeout expired while acquiring edef data.")
            time.sleep(0.01)
        buffers = self.edef.get_buffer(self.pv_list)
        self.assertEqual(len(buffers), len(self.pv_list))
        for pv in buffers:
            self.assertEqual(len(buffers[pv]), self.num_meas)
        for pv in self.pv_list:
            self.assertTrue(pv in buffers)
        
    def tearDown(self):
        try:
            self.edef.release()
        except:
            pass        
        
if __name__ == '__main__':
    unittest.main()
