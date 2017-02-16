edef
====
This module lets you interact with the LCLS Event Definition system, to collect
BSA data.  By instantiating an EventDefinition object, you'll reserve an event
definition.  The EventDefinition object has properties for the event definition
parameters, like number of averages, number of measurements, exclusion and
inclusion masks, etc.  After configuring your event definition, you can call
start() to start collecting data.  You can be notified when data collection is
complete via a callback function, or by calling is_acquisition_complete().