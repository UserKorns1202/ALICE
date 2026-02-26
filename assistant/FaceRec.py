import os
import cv2
import face_recognition

running = True

def sendName(name):
    with open("face_command.txt", "w") as f:
        f.write(name)

# Get a reference to the webcam
video_capture = cv2.VideoCapture(0)

# Load known faces and their names
known_face_encodings = []
known_face_names = []
known_faces_dir = "/ALICE/assets/faces/"  # Directory containing known face images

# Load known faces from directory
for filename in os.listdir(known_faces_dir):
    name = os.path.splitext(filename)[0]  # Remove file extension to get name
    image_path = os.path.join(known_faces_dir, filename)
    image = face_recognition.load_image_file(image_path)
    face_encoding = face_recognition.face_encodings(image)[0]
    known_face_encodings.append(face_encoding)
    known_face_names.append(name)

# Initialize variables
face_locations = []
face_encodings = []
face_names = []

while running:
    # Grab a single frame of video
    ret, frame = video_capture.read()

    # Find all the faces and face encodings in the current frame
    face_locations = face_recognition.face_locations(frame)
    face_encodings = face_recognition.face_encodings(frame, face_locations)

    face_names = []
    for face_encoding in face_encodings:
        # See if the face matches any known faces
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        name = "Unknown"

        # If a match is found, use the name of the known face
        if True in matches:
            first_match_index = matches.index(True)
            name = known_face_names[first_match_index]

        face_names.append(name)
        sendName(name)

        # Exit the loop after obtaining the face name
        running = False

    # Display the results
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        # Draw a box around the face
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)

        # Draw a label with a name below the face
        cv2.rectangle(frame, (left, bottom - 25), (right, bottom), (0, 0, 255), cv2.FILLED)
        font = cv2.FONT_HERSHEY_DUPLEX
        cv2.putText(frame, name, (left + 6, bottom - 6), font, 0.5, (255, 255, 255), 1)

    # Display the resulting image
    cv2.imshow('Video', frame)

    # Break the loop if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the video capture object and close the window
video_capture.release()
cv2.destroyAllWindows()
