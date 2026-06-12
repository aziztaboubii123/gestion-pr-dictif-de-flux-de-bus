from ultralytics import YOLO

model = YOLO('best.pt')
results = model.val(data='data.yaml', plots=True)
print("Terminé. Les courbes sont dans runs/detect/val/")