edef
====
This module lets you interact with the LCLS Event Definition system or LCLS-II BSA Buffer system
to collect BSA data.  By creating a new EventDefinition or BSABuffer object, you'll reserve a
free event definition.  Or, if you want to use an existing event defintion/BSA Buffer, pass the
'edef_number' parameter in when you are making the EventDefinition, or 'number' parameter when
you are making the BSABuffer.

The EventDefinition and BSABuffer objects have properties for the event definition
parameters, like number of averages, number of measurements, exclusion and
inclusion masks, etc.  If you specified an 'edef_number' and connected to an
existing event definition, the existing values are kept when the object is
created.

After configuring your event definition, you can call
start() to start collecting data.  You can be notified when data collection is
complete via a callback function, or by calling is_acquisition_complete().
