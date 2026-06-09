import face_recognition
import numpy as np
import cv2
import base64
import os

CONFIDENCE_THRESHOLD = 0.50   # Lower = stricter (0.45–0.55 is a good range)
FACE_DIR = "student_faces"


def encode_face_from_file(image_path):
    """
    Loads an image file and returns the 128-d face encoding as a Python list.
    Returns (encoding_list, error_message).
    error_message is None on success.
    """
    if not os.path.exists(image_path):
        return None, "Image file not found."

    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)

    if len(encodings) == 0:
        return None, "No face detected in the image. Please use a clear, front-facing photo."
    if len(encodings) > 1:
        return None, "Multiple faces detected. Please use a photo with only one person."

    return encodings[0].tolist(), None


def identify_face_from_base64(b64_data, known_data):
    """
    Receives a base64 JPEG frame from the browser and a list of
    (student_id, student_name, encoding_list) tuples.

    Returns a dict:
      { "matched": True/False, "student_id": int|None, "student_name": str|None,
        "confidence": float|None, "message": str }
    """
    if not known_data:
        return {"matched": False, "student_id": None, "student_name": None,
                "confidence": None, "message": "No students enrolled yet."}

    # Decode base64 → numpy image
    try:
        header, encoded = b64_data.split(",", 1) if "," in b64_data else ("", b64_data)
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
        frame_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame_bgr is None:
            return {"matched": False, "student_id": None, "student_name": None,
                    "confidence": None, "message": "Could not decode image."}
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    except Exception as e:
        return {"matched": False, "student_id": None, "student_name": None,
                "confidence": None, "message": f"Image decode error: {str(e)}"}

    # Detect faces in the frame
    face_locations = face_recognition.face_locations(frame_rgb, model="hog")
    if not face_locations:
        return {"matched": False, "student_id": None, "student_name": None,
                "confidence": None, "message": "No face detected in frame."}

    face_encodings = face_recognition.face_encodings(frame_rgb, face_locations)

    # Build arrays from known data
    known_ids = [row[0] for row in known_data]
    known_names = [row[1] for row in known_data]
    known_encodings = [np.array(row[2]) for row in known_data]

    # Try to match each detected face against the known faces
    for face_enc in face_encodings:
        distances = face_recognition.face_distance(known_encodings, face_enc)
        best_idx = int(np.argmin(distances))
        best_distance = float(distances[best_idx])
        confidence = round((1 - best_distance) * 100, 1)

        if best_distance <= CONFIDENCE_THRESHOLD:
            return {
                "matched": True,
                "student_id": known_ids[best_idx],
                "student_name": known_names[best_idx],
                "confidence": confidence,
                "message": "Match found"
            }

    return {"matched": False, "student_id": None, "student_name": None,
            "confidence": None, "message": "Face not recognized."}


def save_student_photo(file_storage, roll_number):
    """
    Saves an uploaded photo to student_faces/<roll_number>.jpg
    Returns the saved path.
    """
    os.makedirs(FACE_DIR, exist_ok=True)
    filename = f"{roll_number}.jpg"
    path = os.path.join(FACE_DIR, filename)
    file_storage.save(path)
    return path
