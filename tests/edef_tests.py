import unittest
import edef
import os
import epics
import time
from random import randint

class EdefReservationTest(unittest.TestCase):
	def setUp(self):
		(self.sys, self.accelerator) = edef.get_system()
		if self.accelerator == 'LCLS':
			self.ioc_location = 'IN20'
		self.initial_edefs_available = epics.caget("IOC:{iocloc}:EV01:EDEFAVAIL".format(iocloc=self.ioc_location))
		self.name = "edef.py unit tests {}".format(randint(0,255))
		self.edef = edef.EventDefinition(self.name, os.uname()[1])

	def test_available_count_drops(self):
		edefs_available_after_setup = epics.caget("IOC:{iocloc}:EV01:EDEFAVAIL".format(iocloc=self.ioc_location))
		self.assertTrue(edefs_available_after_setup < self.initial_edefs_available)
	
	def test_edef_name_is_correct(self):
		name_pv = "EDEF:{sys}:{num}:NAME".format(sys=self.edef.sys, num=self.edef.edef_num)
		fetched_name = epics.caget(name_pv)
		self.assertEqual(self.name, fetched_name)

	def tearDown(self):
		#Always try to release the event definition at the end of the test.
		try:
			self.edef.release()
		except:
			pass


class EdefReleaseTest(unittest.TestCase):
	def setUp(self):
		(self.sys, self.accelerator) = edef.get_system()
		if self.accelerator == 'LCLS':
			self.ioc_location = 'IN20'
		self.edef = edef.EventDefinition("edef.py unit tests " + str(randint(0,255)), os.uname()[1])
	
	def test_release(self):
		edefs_available_before_release = epics.caget("IOC:{iocloc}:EV01:EDEFAVAIL".format(iocloc=self.ioc_location))
		if not self.edef.is_reserved():
			raise RuntimeError('EDEF could not be reserved, cannot proceed with test.')

		self.edef.release()
		edefs_available_after_release = epics.caget("IOC:{iocloc}:EV01:EDEFAVAIL".format(iocloc=self.edef.ioc_location))
		self.assertEqual(edefs_available_before_release, edefs_available_after_release - 1)

	def tearDown(self):
		try: 
			self.edef.release()
		except:
			pass

class EdefPropertiesTest(unittest.TestCase):
	def setUp(self):
		self.edef = edef.EventDefinition("edef.py unit tests " + str(randint(0,255)), os.uname()[1])
	
	def test_n_avg(self):
		n_avg = 5
		self.edef.n_avg = n_avg
		self.assertEqual(epics.caget("EDEF:{sys}:{num}:AVGCNT".format(sys=self.edef.sys, num=self.edef.edef_num)), n_avg)
		self.assertEqual(self.edef.n_avg, n_avg)
	
	def test_n_measurements(self):
		n_measurements = 10
		self.edef.n_measurements = n_measurements
		self.assertEqual(epics.caget("EDEF:{sys}:{num}:MEASCNT".format(sys=self.edef.sys, num=self.edef.edef_num)), n_measurements)
		self.assertEqual(self.edef.n_measurements, n_measurements)

	def test_inclusion_masks(self):
		self.assertTrue(self.edef.is_reserved())
		mask_1 = epics.caget("EDEF:{sys}:{num}:INCM1.DESC".format(sys=self.edef.sys, num=self.edef.edef_num))
		mask_2 = epics.caget("EDEF:{sys}:{num}:INCM2.DESC".format(sys=self.edef.sys, num=self.edef.edef_num))
		masks = [mask_1, mask_2]
		self.edef.inclusion_masks = masks
		read_mask_1 = epics.caget("EDEF:{sys}:{num}:INCM1".format(sys=self.edef.sys, num=self.edef.edef_num))
		read_mask_2 = epics.caget("EDEF:{sys}:{num}:INCM2".format(sys=self.edef.sys, num=self.edef.edef_num))
		self.assertEqual(read_mask_1, 1)
		self.assertEqual(read_mask_2, 1)
	
	def test_exclusion_masks(self):
		self.assertTrue(self.edef.is_reserved())
		mask_1 = epics.caget("EDEF:{sys}:{num}:INCM1.DESC".format(sys=self.edef.sys, num=self.edef.edef_num))
		mask_2 = epics.caget("EDEF:{sys}:{num}:INCM2.DESC".format(sys=self.edef.sys, num=self.edef.edef_num))
		masks = [mask_1, mask_2]
		self.edef.exclusion_masks = masks
		read_mask_1 = epics.caget("EDEF:{sys}:{num}:EXCM1".format(sys=self.edef.sys, num=self.edef.edef_num))
		read_mask_2 = epics.caget("EDEF:{sys}:{num}:EXCM2".format(sys=self.edef.sys, num=self.edef.edef_num))
		self.assertEqual(read_mask_1, 1)
		self.assertEqual(read_mask_2, 1)

	def tearDown(self):
		try:
			self.edef.release()
		except:
			pass


class AcquisitionTest(unittest.TestCase):
	def setUp(self):
		self.num_meas = 55
		self.edef = edef.EventDefinition("edef.py unit tests " + str(randint(0,255)), user=os.uname()[1], avg=1, measurements=self.num_meas)
		self.pv_list = ["BPMS:UND1:{}90:X".format(num) for num in range(1,34)]

	def test_single_acquisition(self):
		if self.edef.sys != "SYS0":
			print("Acquisition test only works on the LCLS network right now, skipping.")
			return
		self.edef.start()
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
