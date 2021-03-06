#!/bin/sh
#
# Copyright (c) 2016
# Author: Victor Arribas <v.arribas.urjc@gmail.com>
# License: GPLv3 <http://www.gnu.org/licenses/gpl-3.0.html>

world=vacuum.world

gzserver --verbose --minimal_comms $world &
sleep 10 # up to 20 for circuit.world

[ "$1" = "GUI" ] && gzclient &

python2 vacuum.py --Ice.Config=vacuum.cfg &

python2 referee.py --Ice.Config=vacuum.cfg 

#python2 graphicPercentaje.py --Ice.Config=vacuum.cfg

killall gzserver
killall python2
[ "$1" = "GUI" ] && killall gzclient
