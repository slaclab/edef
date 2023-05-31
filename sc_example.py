from edef import BSABuffer
import time

my_buffer = BSABuffer("Matt's Buffer", user="mgibbs") #Will raise an exception if no buffers available.

# You can set destination masks with a list of destination names.
# The names are case sensitive, so watch out!
my_buffer.destination_masks = ["LASER", "SC_DIAG0"]

# Set number of measurements to acquire.  Your value will be clipped to the
# limits of the BSA system.
my_buffer.n_measurements = 500

# You can set a number of shots to average for each measurement.
# Total number of shots to acquire will be n_measurements * n_avg.
my_buffer.n_avg = 10

# +

# Now, start the acquisition.
my_buffer.start()
# Wait for the buffer to collect all 500 points.  Alternatively, you can 
# set a callback function to run when acquisition is complete instead.
while not my_buffer.is_acquisition_complete():
    time.sleep(0.1)
print(my_buffer.get_data_buffer("BPMS:GUNB:314:X"))
print(len(my_buffer.get_data_buffer("BPMS:GUNB:314:X")))
# -



def my_done_callback():
    print(my_buffer.get_data_buffer("BPMS:GUNB:314:X"))

my_buffer.done_callback = my_done_callback
my_buffer.start()

#You can use the buffer object to get the acquired data for your buffer.
gunb_bpm_data = my_buffer.get_data_buffer("BPMS:GUNB:314:X")
print(gunb_bpm_data)


#Please release your buffer when you are done!
my_buffer.release()

# You can also use an event definition using python's "with" keyword.
# This will automatically release the buffer when the "with" block is complete.
# Really, you should probably just use this all the time, unless you have
# a good reason to keep your buffer around for a long time.
with BSABuffer("Matt's BSA", user="mgibbs") as my_other_buffer:
    my_other_buffer.n_measurements = 500
    my_other_buffer.start()
    while not my_other_buffer.is_acquisition_complete():
        time.sleep(0.1)
    data = my_other_buffer.get_data_buffer("BPMS:GUNB:314:X")
    print(data)
#When you exit the "with" block, the buffer releases itself.


