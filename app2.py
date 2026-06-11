# -*- coding: utf-8 -*-
"""
app.py - DMS YOLOv8 ONNX | Envoi MQTT uniquement du nom de l'événement
"""

import sys
import time
import argparse
import collections
import threading

import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    print("[ERREUR] pip install onnxruntime")
    sys.exit(1)

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[ERREUR] pip install paho-mqtt==1.6.1")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration MQTT HiveMQ
# ---------------------------------------------------------------------------
MQTT_BROKER    = "broker.hivemq.com"
MQTT_PORT      = 1883
MQTT_TOPIC     = "dms/alertes"
MQTT_CLIENT_ID = "jetson-dms-001"
ALERT_COOLDOWN = 3.0

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

CLASS_COLORS = {
    0: (0, 200, 0),
    1: (0, 0, 255),
    2: (0, 140, 255),
    3: (0, 0, 220),
    4: (200, 200, 0),
}

DANGER_CLASSES = {1, 2, 3}

ALERTS = {
    1: "ALERTE : Yeux fermes !",
    2: "ALERTE : Cigarette detectee !",
    3: "ALERTE : Telephone detecte !",
}

# Événements simples (strings)
MQTT_EVENTS = {
    1: "closed_eye",
    2: "cigarette",
    3: "phone",
}

# ---------------------------------------------------------------------------
# Client MQTT modifié (envoi simple string)
# ---------------------------------------------------------------------------
class MQTTClient(object):
    def __init__(self):
        self.client    = mqtt.Client(client_id=MQTT_CLIENT_ID)
        self.connected = False
        self.last_sent = {}

        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._connect()

    def _connect(self):
        try:
            print("[MQTT] Connexion a {}:{}...".format(MQTT_BROKER, MQTT_PORT))
            self.client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print("[MQTT] Erreur connexion : {}".format(e))

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print("[MQTT] Connecte au broker HiveMQ")
        else:
            print("[MQTT] Echec connexion, code : {}".format(rc))

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        print("[MQTT] Deconnecte")

    def send_alert(self, cls_id):
        now  = time.time()
        last = self.last_sent.get(cls_id, 0)
        if now - last < ALERT_COOLDOWN:
            return
        if not self.connected:
            print("[MQTT] Non connecte, alerte ignoree")
            return

        # ⚡ Modification : on envoie simplement la chaîne de l'événement
        payload = MQTT_EVENTS.get(cls_id, "unknown")

        def _pub():
            result = self.client.publish(MQTT_TOPIC, payload, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print("[MQTT] Alerte envoyee -> {} : {}".format(MQTT_TOPIC, payload))
            else:
                print("[MQTT] Echec envoi code : {}".format(result.rc))

        threading.Thread(target=_pub, daemon=True).start()
        self.last_sent[cls_id] = now

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        print("[MQTT] Deconnexion propre")


# ---------------------------------------------------------------------------
# Le reste du code (détection, dessin, etc.) est identique à l'original
# Je le recopie ci-dessous sans modifications
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
    pred    = output[0].transpose()
    boxes   = pred[:, :4]
    scores  = pred[:, 4:]

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


def draw(frame, detections):
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


def draw_alerts(frame, detected_classes, danger_counter, mqtt_client):
    alert_y    = 60
    any_danger = False

    for cls_id in DANGER_CLASSES:
        if cls_id in detected_classes:
            danger_counter[cls_id] = danger_counter.get(cls_id, 0) + 1
        else:
            danger_counter[cls_id] = 0

        if danger_counter[cls_id] >= 10:
            any_danger = True
            msg   = ALERTS[cls_id]
            color = CLASS_COLORS[cls_id]

            mqtt_client.send_alert(cls_id)

            overlay = frame.copy()
            cv2.rectangle(overlay, (0, alert_y - 28), (530, alert_y + 5),
                          color, -1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

            cv2.putText(frame, msg, (10, alert_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
            cv2.putText(frame, "[MQTT->HiveMQ]", (10, alert_y + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

            alert_y += 55

    if any_danger:
        t = int(time.time() * 3) % 2
        if t == 0:
            cv2.rectangle(frame, (0, 0),
                          (frame.shape[1] - 1, frame.shape[0] - 1),
                          (0, 0, 255), 4)

    return danger_counter


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


def run(sess, img_size, source, conf_thres, iou_thres, mqtt_client):
    input_name     = sess.get_inputs()[0].name
    danger_counter = {}
    fps_buf        = collections.deque(maxlen=30)

    cap_src = int(source) if str(source).isdigit() else source
    cap     = cv2.VideoCapture(cap_src)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("[ERREUR] Impossible d'ouvrir la source : {}".format(source))
        mqtt_client.disconnect()
        sys.exit(1)

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
        danger_counter   = draw_alerts(frame, detected_classes,
                                       danger_counter, mqtt_client)

        if mqtt_client.connected:
            cv2.putText(frame, "MQTT: OK", (frame.shape[1] - 140, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "MQTT: OFF", (frame.shape[1] - 140, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        fps = 1.0 / (time.time() - t0 + 1e-6)
        fps_buf.append(fps)
        cv2.putText(frame, "FPS: {:.1f}".format(sum(fps_buf) / len(fps_buf)),
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imshow("DMS - Driver Monitoring System", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    mqtt_client.disconnect()


def main():
    p = argparse.ArgumentParser(description="DMS YOLOv8 ONNX + MQTT HiveMQ (evenement simple)")
    p.add_argument('--weights',    default='best2.onnx',
                   help='Chemin vers le modele .onnx')
    p.add_argument('--source',     default='0',
                   help='Index webcam (0,1...) ou chemin video/image')
    p.add_argument('--conf-thres', type=float, default=0.25,
                   help='Seuil de confiance')
    p.add_argument('--iou-thres',  type=float, default=0.45,
                   help='Seuil IoU NMS')
    args = p.parse_args()

    mqtt_client = MQTTClient()
    time.sleep(2)

    sess, img_size = load_model(args.weights)
    run(sess, img_size, args.source,
        args.conf_thres, args.iou_thres, mqtt_client)


if __name__ == '__main__':
    main()
