#!/bin/bash

#sudo chmod a+rw /dev/ttyUSB0
#sudo mkdosfs /dev/mmcblk0p1  -F32

rlwrap=$(which rlwrap)

if [[ -z $rlwrap ]]; then
	echo '### Install rlwrap for better experience';
fi;

$rlwrap python3.5 main.py $@
