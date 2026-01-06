import json
import os
import difflib
import re


DB_FILE = "fda_database.json"

def load_database():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

DRUG_DB = load_database()

def analyze_metadata(detections):
    
    best_record = None  
    highest_score = 0.0
    
    strength = "N/A"
    quantity = "N/A"
    expiry = "N/A"

    for d in detections:
        text = d['text']
        
        # 1. Entity Linking 
        for record in DRUG_DB:
            # This will use the brand name for matching and take the record with the highest similarirty 
            # Calculate similarity score for brandname
            target_name = record['brand_name']
            score = difflib.SequenceMatcher(None, target_name.lower(), text.lower()).ratio() # 0 to 1
            
            # Boost score if exact match found
            if target_name.lower() in text.lower():
                score = 0.95 
            
            if score > highest_score:
                highest_score = score
                best_record = record # Save best matching record using brand name

        # 2. Extract Strength, Quanity, Expiry

        #d+ is for digits, \s* is for optional spaces, and units
        s_match = re.search(r'(\d+)\s*(mg|ml|mcg|g)', text, re.I) # I is ignore case
        if s_match: strength = s_match.group(0) # Full match
        
        q_match = re.search(r'(\d+)\s*(capsules|tablets|pills|vien)', text, re.I)
        if q_match: quantity = q_match.group(0) 

        e_match = re.search(r'(EXP|HSD|Expiry)[\s:]*(\d+/\d+)', text, re.I)
        if e_match: expiry = e_match.group(0)

    # 3. Compile FDA info if a good match is found
    fda_info = None
    if best_record and highest_score > 0.4:
        fda_info = f"""
        Brand Name: {best_record['brand_name']}
        Active Ingredient: {best_record['generic_name']}
        Pharmacological Class: {best_record['pharm_class']}
        Data Source: FDA USA
        """

    return {
        "final_suggestion": best_record['brand_name'] if best_record else "Unknown",
        "score": highest_score,
        "strength": strength,
        "quantity": quantity,
        "expiry": expiry,
        "fda_record": fda_info
    }