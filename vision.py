"""
VietRx Vision Module: Handles real-time medication label detection.
Author: Xuan Thanh Phong Nguyen
Institution: Wright State University
"""

from ultralytics import YOLO
import easyocr
import cv2
import os

# Hyperparameters for Computer Vision Pipeline
MODEL_PATH = "best.pt"
YOLO_CONF_THRESHOLD = 0.45  # Confidence for YOLOV8 detecitons
BOX_PADDING = 20           # Make sure OCR captures the full text area

class VisionSystem:
    def __init__(self):
        """Initializes the YOLOv8 detector and the EasyOCR reader."""
        # Load custom YOLOv8 model for drug label localization
        self.detector = YOLO(MODEL_PATH)
        
        # Initialize EasyOCR (CPU mode for general compatibility)
        self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)

    def extract_text_proposals(self, frame):
        """
        Processes a single frame to extract raw unstructured text.
        Args:
            frame: A numpy array representing the current webcam frame.
        Returns:
            list: A collection of detected text snippets.
        """

        # Check if the YOLO is not loaded or frame is None
        if not self.detector or frame is None:
            return []
        
        # Phase 1: Object Detection (Localization)
        results = self.detector(frame, conf = YOLO_CONF_THRESHOLD, verbose = False)

        # Draw the bouding boxes for debugging
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        cv2.imshow("YOLO debug", frame)
        cv2.waitKey(1)
        candidate_list = []

        for r in results:
            for box in r.boxes:
                # Coordinate extraction
                

                # Take the coordinates of the left-top and rightbottom corners
                # then convert to integer
                x1, y1, x2, y2 = map(int, box.xyxy[0]) 
                
                # Get frame dimensions for increase the bounding box safely
                # _ is for channels that I don't need
                h, w, _ = frame.shape
                
                # Image Cropping with boundary safety checks using dimensions
                cropped = frame[max(0, y1-BOX_PADDING):min(h, y2+BOX_PADDING), 
                               max(0, x1-BOX_PADDING):min(w, x2+BOX_PADDING)]

                # Phase 2: Optical Character Recognition (OCR)
                ocr_data = self.reader.readtext(cropped)
                print(ocr_data)
                
                # ocr_data format: [(bbox, text, confidence)]
                for (_, text, conf_ocr) in ocr_data: # take only the text part
                    if len(text) > 2:  # Ignore very short texts
                        candidate_list.append({"text": text.strip()}) # Store only the text for further processing
                        # [{ "text": "Bexarotene" }, { "text": "75 mg" }, ...]
        return candidate_list 