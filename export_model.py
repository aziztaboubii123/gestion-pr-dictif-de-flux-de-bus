from ultralytics import YOLO

# Load your model
model = YOLO('best.pt')

# Export to ONNX format
model.export(format='onnx', opset=12, imgsz=640)

print("Export completed successfully!")