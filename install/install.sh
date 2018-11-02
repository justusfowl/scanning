#!/bin/bash

echo "What is the python path for execution?"
read EXECPYPATH

echo "The path $EXECPYPATH will be set for python"

WDPATH=$(dirname `pwd`)

sed -e "s;%EXECPYPATH%;$EXECPYPATH;g" -e "s;%WDPATH%;$WDPATH;g" scanning_mailbox.service.tpl > scanning_mailbox.service
sed -e "s;%EXECPYPATH%;$EXECPYPATH;g" -e "s;%WDPATH%;$WDPATH;g" scanning_ocrprocess.service.tpl > scanning_ocrprocess.service
sed -e "s;%EXECPYPATH%;$EXECPYPATH;g" -e "s;%WDPATH%;$WDPATH;g" scanning_monitoring.service.tpl > scanning_monitoring.service

cp scanning_*.service /lib/systemd/system

echo "Service files created"

systemctl enable scanning_mailbox.service
systemctl enable scanning_ocrprocess.service
systemctl enable scanning_monitoring.service

systemctl start scanning_mailbox.service
systemctl start scanning_ocrprocess.service
systemctl start scanning_monitoring.service

echo "Services enabled and started" 
