del -r dist
pip install pyinstaller
pip install -r requirements.txt

pyinstaller --onefile -w .\tacref-exporter.py
# Compress-Archive -Update .\"tac-ref exporter 1.0"\ "tac-ref exporter 1.0.zip"