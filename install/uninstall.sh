systemctl stop scanning_ocrprocess.service
systemctl stop scanning_monitoring.service
systemctl stop scanning_mailbox.service

systemctl disable scanning_ocrprocess.service
systemctl disable scanning_monitoring.service
systemctl disable scanning_mailbox.service


rm /lib/systemd/system/scanning_ocrprocess.service
rm /lib/systemd/system/scanning_monitoring.service
rm /lib/systemd/system/scanning_mailbox.service

systemctl daemon-reload
echo "scanning services succesfully uninstalled"
