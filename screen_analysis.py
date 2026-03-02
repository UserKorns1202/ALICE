"""Screen analysis helpers. Heavy dependencies are optional and will be
gracefully degraded if not available (so the main program can start).
"""
try:
    import pyautogui
    import cv2
    import numpy as np
    import easyocr
    screen_analysis_available = True
except Exception:
    pyautogui = None
    cv2 = None
    np = None
    easyocr = None
    screen_analysis_available = False
    print("Optional screen analysis dependencies not available; features disabled")

# Paths to YOLO/EAST model files (used only when modules available)
YOLO_CFG_PATH = 'yolov3.cfg'
YOLO_WEIGHTS_PATH = 'yolov3.weights'
YOLO_CLASSES_PATH = 'coco.names'
EAST_MODEL_PATH = 'frozen_east_text_detection.pb'

# Lazy-loaded model handles
net = None
layer_names = None
output_layers = None
east_net = None
reader = None

def _ensure_models_loaded():
    global net, layer_names, output_layers, east_net, reader
    if not screen_analysis_available:
        return False
    try:
        if net is None:
            net = cv2.dnn.readNet(YOLO_WEIGHTS_PATH, YOLO_CFG_PATH)
            layer_names = net.getLayerNames()
            unconnected_layers = net.getUnconnectedOutLayers()
            if isinstance(unconnected_layers, np.ndarray):
                output_layers = [layer_names[i - 1] for i in unconnected_layers.flatten()]
            else:
                output_layers = [layer_names[unconnected_layers - 1]]
        if east_net is None:
            east_net = cv2.dnn.readNet(EAST_MODEL_PATH)
        if reader is None:
            reader = easyocr.Reader(['en'])
        return True
    except Exception:
        return False

def capture_screen():
    """Capture the current screen and return as an image."""
    if not screen_analysis_available or not _ensure_models_loaded():
        raise RuntimeError("Screen analysis not available (missing dependencies or models)")
    screenshot = pyautogui.screenshot()
    frame = np.array(screenshot)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return frame

def detect_objects(frame):
    """Detect objects in the frame using YOLO."""
    if not screen_analysis_available or not _ensure_models_loaded():
        return [], [], [], []
    height, width, channels = frame.shape
    blob = cv2.dnn.blobFromImage(frame, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
    net.setInput(blob)
    outs = net.forward(output_layers)

    class_ids = []
    confidences = []
    boxes = []

    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > 0.5:
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                x = int(center_x - w / 2)
                y = int(center_y - h / 2)
                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)

    indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
    return indices, class_ids, boxes, confidences

def detect_text(frame):
    """Detect text in the frame using EasyOCR."""
    if not screen_analysis_available or not _ensure_models_loaded():
        return []
    text_results = reader.readtext(frame)
    detected_texts = []
    for (bbox, text, prob) in text_results:
        if prob > 0.5:  # Only include text with high confidence
            detected_texts.append(text)
    return detected_texts

def identify_screen():
    """Capture screen, detect objects, and detect text."""
    try:
        frame = capture_screen()
    except RuntimeError:
        return []
    # Detect text
    detected_texts = detect_text(frame)
    if detected_texts:
        print("Detected text:", detected_texts)
    return detected_texts

def game_detection_loop(listen_function, speak_function):
    """Continuous loop to detect games and handle visor toggling."""
    print("Starting game detection loop...")
    game_active = False

    while True:
        detected_texts = identify_screen()

        if detected_texts:  # If any text is detected
            if any("STRATAGEMS" in text for text in detected_texts):  # Replace with your game's identifier text
                if not game_active:
                    print("Game detected: Helldivers. You can say 'Toggle Visor' to execute the command.")
                    game_active = True
            else:
                if game_active:
                    print("Game exited. Ending game detection loop.")
                    break
                print("No recognized game detected.")
        else:
            if game_active:
                print("Game exited. Ending game detection loop.")
                break
            print("No text detected.")

        if game_active:
            # Listen for the toggle visor command
            print("Listening for command...")
            command = listen_function()
            if command and "toggle visor" in command.lower():
                print("Command received: Toggle Visor")
                speak_function("Visor toggled.")
                pyautogui.hotkey('ctrl', 'n')

        # Simulate a delay between checks
        cv2.waitKey(1000)  # Wait for 1 second

    print("Game detection loop has ended.")
