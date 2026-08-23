import pytesseract
from PIL import Image
import os

# Tesseract Executable Path (Windows)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_from_image(image_path: str):
    if not os.path.exists(image_path):
        return {"error": f"Image file '{image_path}' not found! Please place 'sample.jpg' in the folder."}
    
    # Image open karo
    img = Image.open(image_path)
    
    # Tesseract se text + bounding boxes extract karo
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    
    ocr_blocks = []
    n_boxes = len(data['text'])
    
    for i in range(n_boxes):
        text = data['text'][i].strip()
        confidence = float(data['conf'][i])
        
        # Meaningful text filter (ignore empty spaces & low confidence noise)
        if text and confidence > 30:
            ocr_blocks.append({
                "block_id": f"b_{i}",
                "text": text,
                "box": [data['left'][i], data['top'][i], data['width'][i], data['height'][i]],
                "ocr_confidence": round(confidence / 100.0, 2)
            })
            
    return ocr_blocks

# Actual Image Test Run
if __name__ == "__main__":
    print("Running Image OCR Test on sample.jpg...\n")
    results = extract_text_from_image("sample.jpg")
    
    if isinstance(results, dict) and "error" in results:
        print(results["error"])
    else:
        print("--- EXTRACTED TEXT FROM IMAGE ---")
        for block in results:
            print(f"ID: {block['block_id']} | Text: {block['text']} | Conf: {block['ocr_confidence']}")