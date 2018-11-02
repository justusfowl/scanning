[Unit]
Description=Scanning | Jobs for watching input directories

[Service]
Type=simple
ExecStart=%EXECPYPATH% %WDPATH% -r monitor -d /mnt/EicScanRaw /mnt/KirScanRaw
WorkingDirectory=%WDPATH%
Restart=always
RestartSec=3

[Install]
WantedBy=sysinit.target
