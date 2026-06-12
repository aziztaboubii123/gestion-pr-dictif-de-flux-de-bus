# -*- coding: utf-8 -*-
"""
detect_onnx.py — DMS YOLOv8 ONNX | Python 3.6 | Sans ultralytics
Classes : Open Eye, Closed Eye, Cigarette, Phone, Seatbelt
"""

import sys
import time
import argparse
import collections

import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    print("[ERREUR] pip install onnxruntime")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Classes et configuration DMS
# ---------------------------------------------------------------------------

CLASS_NAMES = [
    "Open Eye",    # 0
    "Closed Eye",  # 1
    "Cigarette",   # 2
    "Phone",       # 3
    "Seatbelt",    # 4
]

# Couleur BGR par classe
CLASS_COLORS = {
    0: (0, 200, 0),      # Open Eye    -> vert
    1: (0, 0, 255),      # Closed Eye  -> rouge
    2: (0, 140, 255),    # Cigarette   -> orange
    3: (0, 0, 220),      # Phone       -> rouge vif
    4: (200, 200, 0),    # Seatbelt    -> cyan
}

# Classes dangereuses -> alerte
DANGER_CLASSES = {1, 2, 3}  # Closed Eye, Cigarette, Phone

# Alertes texte
ALERTS = {
    1: "ALERTE : Yeux fermes !",
    2: "ALERTE : Cigarette detectee !",
    3: "ALERTE : Telephone detecte !",
}


# ---------------------------------------------------------------------------
# Pre-traitement
# ---------------------------------------------------------------------------

def letterbox(img, new_shape=640, color=(114, 114, 114)):
    h, w = img.shape[:2]
    r = min(new_shape / h, new_shape / w)
    new_unpad = (int(round(w * r)), int(round(h * r)))
    dw = (new_shape - new_unpad[0]) / 2
    dh = (new_shape - new_unpad[1]) / 2
    if (w, h) != new_unpad:
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top    = int(round(dh - 0.1))
    bottom = int(round(dh + 0.1))
    left   = int(round(dw - 0.1))
    right  = int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right,
                             cv2.BORDER_CONSTANT, value=color)
    return img, r, (dw, dh)


def preprocess(frame, img_size=640):
    img, ratio, pad = letterbox(frame, img_size)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    img = np.transpose(img, (2, 0, 1))
    img = np.ascontiguousarray(img[np.newaxis])
    return img, ratio, pad


# ---------------------------------------------------------------------------
# Post-traitement YOLOv8
# ---------------------------------------------------------------------------

def _nms(boxes, scores, iou_thres):
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas  = (x2 - x1 + 1) * (y2 - y1 + 1)
    order  = scores.argsort()[::-1]
    keep   = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w_   = np.maximum(0.0, xx2 - xx1 + 1)
        h_   = np.maximum(0.0, yy2 - yy1 + 1)
        iou  = (w_ * h_) / (areas[i] + areas[order[1:]] - w_ * h_)
        inds  = np.where(iou <= iou_thres)[0]
        order = order[inds + 1]
    return keep


def postprocess(output, orig_shape, ratio, pad,
                conf_thres=0.25, iou_thres=0.45):
    pred = output[0].transpose()       # [8400, 4+nc]
    boxes  = pred[:, :4]
    scores = pred[:, 4:]

    cls_ids = np.argmax(scores, axis=1)
    confs   = scores[np.arange(len(cls_ids)), cls_ids]

    mask    = confs > conf_thres
    boxes   = boxes[mask]
    confs   = confs[mask]
    cls_ids = cls_ids[mask]

    if len(boxes) == 0:
        return []

    x1 = boxes[:, 0] - boxes[:, 2] / 2
    y1 = boxes[:, 1] - boxes[:, 3] / 2
    x2 = boxes[:, 0] + boxes[:, 2] / 2
    y2 = boxes[:, 1] + boxes[:, 3] / 2
    xyxy = np.stack([x1, y1, x2, y2], axis=1)

    keep    = _nms(xyxy, confs, iou_thres)
    xyxy    = xyxy[keep]
    confs   = confs[keep]
    cls_ids = cls_ids[keep]

    h_orig, w_orig = orig_shape[:2]
    xyxy[:, [0, 2]] -= pad[0]
    xyxy[:, [1, 3]] -= pad[1]
    xyxy /= ratio
    xyxy[:, 0] = np.clip(xyxy[:, 0], 0, w_orig)
    xyxy[:, 1] = np.clip(xyxy[:, 1], 0, h_orig)
    xyxy[:, 2] = np.clip(xyxy[:, 2], 0, w_orig)
    xyxy[:, 3] = np.clip(xyxy[:, 3], 0, h_orig)

    results = []
    for i in range(len(xyxy)):
        results.append([
            int(xyxy[i, 0]), int(xyxy[i, 1]),
            int(xyxy[i, 2]), int(xyxy[i, 3]),
            float(confs[i]), int(cls_ids[i])
        ])
    return results


# ---------------------------------------------------------------------------
# Annotation + alertes DMS
# ---------------------------------------------------------------------------

def draw(frame, detections):
    """Dessine les boxes et retourne l'ensemble des classes detectees."""
    detected_classes = set()

    for x1, y1, x2, y2, conf, cls_id in detections:
        detected_classes.add(cls_id)
        color = CLASS_COLORS.get(cls_id, (200, 200, 200))
        name  = CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else str(cls_id)
        label = "{} {:.0f}%".format(name, conf * 100)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw, y1), color, -1)
        cv2.putText(frame, label, (x1, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    return detected_classes


def draw_alerts(frame, detected_classes, danger_counter):
    """
    Affiche les alertes DMS en haut de l'ecran.
    danger_counter : dict {cls_id: nb_frames_consecutives}
    Une alerte s'affiche apres 10 frames consecutives de detection.
    """
    alert_y = 60
    any_danger = False

    for cls_id in DANGER_CLASSES:
        if cls_id in detected_classes:
            danger_counter[cls_id] = danger_counter.get(cls_id, 0) + 1
        else:
            danger_counter[cls_id] = 0

        # Alerte apres 10 frames consecutives (~0.3s a 30fps)
        if danger_counter[cls_id] >= 10:
            any_danger = True
            msg   = ALERTS[cls_id]
            color = CLASS_COLORS[cls_id]

            # Fond semi-transparent
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, alert_y - 28), (500, alert_y + 5),
                          color, -1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

            cv2.putText(frame, msg, (10, alert_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                        (255, 255, 255), 2)
            alert_y += 40

    # Bordure rouge clignotante si danger
    if any_danger:
        t = int(time.time() * 3) % 2  # clignote a 1.5Hz
        if t == 0:
            cv2.rectangle(frame, (0, 0),
                          (frame.shape[1]-1, frame.shape[0]-1),
                          (0, 0, 255), 4)

    return danger_counter


# ---------------------------------------------------------------------------
# Chargement ONNX
# ---------------------------------------------------------------------------

def load_model(onnx_path):
    providers = ['CPUExecutionProvider']
    if 'CUDAExecutionProvider' in ort.get_available_providers():
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        print("[INFO] CUDA disponible")

    sess     = ort.InferenceSession(onnx_path, providers=providers)
    inp      = sess.get_inputs()[0]
    img_size = inp.shape[2] if isinstance(inp.shape[2], int) else 640
    print("[OK] Modele charge | input: {} | {} classes".format(
          inp.shape, len(CLASS_NAMES)))
    return sess, img_size


# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------

def run(sess, img_size, source, conf_thres, iou_thres):
    input_name    = sess.get_inputs()[0].name
    danger_counter = {}
    fps_buf        = collections.deque(maxlen=30)

    cap_src = int(source) if str(source).isdigit() else source
    cap     = cv2.VideoCapture(cap_src)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("[INFO] Appuyez sur 'q' pour quitter")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Fin du flux.")
            break

        t0 = time.time()

        tensor, ratio, pad = preprocess(frame, img_size)
        out  = sess.run(None, {input_name: tensor})[0]
        dets = postprocess(out, frame.shape, ratio, pad, conf_thres, iou_thres)

        detected_classes = draw(frame, dets)
        danger_counter   = draw_alerts(frame, detected_classes, danger_counter)

        # FPS
        elapsed = time.time() - t0
        fps = 1.0 / (elapsed + 1e-6)
        fps_buf.append(fps)
        avg_fps = sum(fps_buf) / len(fps_buf)

        cv2.putText(frame, "FPS: {:.1f}".format(avg_fps), (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imshow("DMS — Driver Monitoring", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="DMS YOLOv8 ONNX — Python 3.6")
    p.add_argument('--weights',    default='best2.onnx')
    p.add_argument('--source',     default='0')
    p.add_argument('--conf-thres', type=float, default=0.25)
    p.add_argument('--iou-thres',  type=float, default=0.45)
    args = p.parse_args()

    sess, img_size = load_model(args.weights)
    run(sess, img_size, args.source, args.conf_thres, args.iou_thres)


if __name__ == '__main__':
    main()
