edef
====
This module lets you interact with the LCLS Event Definition system to collect
BSA data.  By creating a new EventDefinition object, you'll reserve a free event
definition.  Or, if you want to use an existing event defintion, pass the
'edef_number' parameter in when you are making the EventDefinition.

The EventDefinition object has properties for the event definition
parameters, like number of averages, number of measurements, exclusion and
inclusion masks, etc.  If you specified an 'edef_number' and connected to an
existing event definition, the existing values are kept when the object is
created.

After configuring your event definition, you can call
start() to start collecting data.  You can be notified when data collection is
complete via a callback function, or by calling is_acquisition_complete().