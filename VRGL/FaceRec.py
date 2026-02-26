import os
import cv2
import face_recognition
import VRGL as ALICE
import torch
from VRGL import username  # reuse dynamic username

# Load the YOLO model for face detection
yolo_model = torch.hub.load('ultralytics/yolov5', 'yolov5s')

def sendName(name):
    with open(os.path.join(os.path.dirname(__file__), "face_command.txt"), "w") as f:
        f.write(name)

# Get a reference to the webcam and set resolution
video_capture = cv2.VideoCapture(0)
video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# Load known faces and their names
known_face_encodings = []
known_face_names = []
known_faces_dir = os.path.join(os.path.dirname(__file__), 'assets', 'faces')  # Directory containing known face images (local to VRGL)

# Load known faces from subdirectories
for person_name in os.listdir(known_faces_dir):
    person_dir = os.path.join(known_faces_dir, person_name)
    if os.path.isdir(person_dir):  # Ensure it's a directory
        for filename in os.listdir(person_dir):
            image_path = os.path.join(person_dir, filename)
            try:
                image = face_recognition.load_image_file(image_path)
                face_encodings = face_recognition.face_encodings(image)
                if face_encodings:
                    known_face_encodings.append(face_encodings[0])
                    known_face_names.append(person_name)  # Use the folder name as the person's name
            except Exception as e:
                print(f"Error processing file {image_path}: {e}")

running = True
frame_count = 0  # To track the number of frames

while running:
    ret, frame = video_capture.read()
    if not ret:
        break

    if frame_count % 5 == 0:  # Process every 5th frame for speed optimization
        # Convert the frame to RGB (YOLO works with BGR but face_recognition needs RGB)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Run YOLO model inference
        results = yolo_model(rgb_frame)
        detections = results.xyxy[0].cpu().numpy()  # Get detected bounding boxes

        face_locations = []
        largest_area = 0
        closest_face = None

        for det in detections:
            x1, y1, x2, y2, conf, cls = det
            if cls == 0 and conf > 0.6:  # Ensure it's a face with high confidence
                area = (x2 - x1) * (y2 - y1)
                if area > largest_area:
                    largest_area = area
                    closest_face = (int(y1), int(x2), int(y2), int(x1))
        
        if closest_face:
            face_locations.append(closest_face)

        # Get face encodings
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        face_names = []

        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
            name = "Unknown"
            if True in matches:
                first_match_index = matches.index(True)
                name = known_face_names[first_match_index]
            
            face_names.append(name)
            sendName(name)
            running = False  # Stop after recognizing a face

    # Display results
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
        cv2.rectangle(frame, (left, bottom - 25), (right, bottom), (0, 0, 255), cv2.FILLED)
        font = cv2.FONT_HERSHEY_DUPLEX
        cv2.putText(frame, name, (left + 6, bottom - 6), font, 0.5, (255, 255, 255), 1)
    
    cv2.imshow('Video', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    
    frame_count += 1

# Cleanup
ALICE.play_sound("aiCameraSound.mp3")
video_capture.release()
cv2.destroyAllWindows()
