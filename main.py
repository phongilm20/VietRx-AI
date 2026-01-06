"""
VietRx Controller: Orchestrates UI, Vision, Logic, and LLM reasoning.
"""

import sys
import os
import cv2
import re  # FIXED: Required for clean_text_for_audio
import platform
from gtts import gTTS

# Configure system path to allow module cross-referencing in subfolders
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import vision
import knowledge
import brain  # Accesses Gemini/LLM API and Safety Auditor
    

# Clean text for TTS
def clean_text_for_audio(text):
    """Sanitizes generated LxLM text for optimal TTS playback."""
    text = re.sub(r'[*#_`]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Audio Synthesis and Playback module
def play_audio(text):
    """Executes cross-platform audio synthesis and playback."""
    try:
        clean_response = clean_text_for_audio(text)
        tts = gTTS(text=clean_response, lang='vi')
        filename = "advice.mp3"
        tts.save(filename)
        
        # Platform-specific execution commands
        if platform.system() == "Windows": os.system(f'start {filename}')
        else: os.system(f'xdg-open {filename}')
    except Exception as e:
        print(f"[ERROR] Audio Service Failure: {e}")

def run_system():
    vs = vision.VisionSystem() #
    cap = cv2.VideoCapture(0)
    
    print("--- VietRx Academic Prototype Ready ---")
    print("Command: Press 's' to Scan Medication, 'q' to Quit.")
    print("Please ensure your medication label is visible to the camera")

    while True:
        ret, frame = cap.read() 
        if not ret: break # Failed to grab frame
        cv2.imshow("VietRx - Real-time Scanning", frame) # Display frame

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'): 

            # Step 1: Text Detection and Extraction
            print("\n[STEP 1] Initializing Vision Pipeline...")
            detections = vs.extract_text_proposals(frame) # Extracted finish text
            
            # Step 2: Analyze the extracted text and link to FDA DB
            print("[STEP 2] Processing data & Entity Linking...")
            data = knowledge.analyze_metadata(detections) # Analyze, evaluate, link
            
            # Print analysis results for debugging/audit
            print(f"[ENTITY] Candidate: '{data['final_suggestion']}' (Conf: {data['score']:.2f})")
            print(f"[INFO] Strength: {data['strength']} | Quantity: {data['quantity']} | Exp: {data['expiry']}")

            # Step 3: Human-in-the-Loop Validation
            confirm = input(f"[INPUT] Confirm identification? (Y/n): ").strip()
            drug_name = data['final_suggestion'] if confirm.lower() in ("y", "yes", "") else confirm

            # Step 4: LLM Advice
            context = f"Drug: {drug_name}, Dosage: {data['strength']}, Qty: {data['quantity']}, Exp: {data['expiry']}"
            print("[STEP 3] Executing LLM Safety Audit & Advice Generation...")
            advice = brain.get_medical_advice(context, data['fda_record']) # take both the context and fda info 
            
            print(f"\n[FINAL OUTPUT]:\n{advice}") 
            play_audio(advice) #

        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_system()