## kDatacenter Mail Processing

Purpose: Digitize all incoming physical mail and letters in order to be able to full-text search all mail through OCR and sandwich PDFs

Requires tesseract and rabbitMQ
Requires python packages (c.f. requirements.txt) 

install -> installation scripts as service under linux


# ScanDirectoryMonitor
Monitor inbound folders for scans from different locations 

# eMailMonitor
Monitor email address, convert attachments into PDF and publish into pipeline

# OCRProcessor
Consume published tasks from the pipeline to process mails, devide multi-paged, diverse letters and derive recipient. Also notify person via email and store letters in their mailbox.
