[Unit]
Description=Scanning | OCR for post and mail

[Service]
Type=simple
ExecStart=/home/uli/anaconda2/envs/scanning/bin/python3 /opt/scanning -r ocrprocess
WorkingDirectory=/opt/scanning/
Restart=always
RestartSec=3

[Install]
WantedBy=sysinit.target