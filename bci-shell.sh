#!/bin/bash

rlwrap=$(which rlwrap)

if [[ -z $rlwrap ]]; then
	echo '### Install rlwrap for better experience';
fi;

$rlwrap python3 main.py
