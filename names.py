# lire_classes.py — a executer UNE FOIS sur Windows
from ultralytics import YOLO
m = YOLO('best.pt')
print(m.names)