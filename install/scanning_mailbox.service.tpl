[Unit]
Description=Scanning | Mailbox retrieval

[Service]
Type=simple
ExecStart=%EXECPYPATH% %WDPATH% -r mailbox
WorkingDirectory=%WDPATH%
Restart=always
RestartSec=3

[Install]
WantedBy=sysinit.target