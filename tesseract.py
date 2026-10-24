import os
import time
import subprocess

desktop_path = "/Users/aa/Desktop"

def run_tesseract(file_path):
    # Run tesseract and capture the output
    result = subprocess.run(["tesseract", file_path, "stdout"], capture_output=True, text=True)
    extracted_text = result.stdout
    
    # Append the extracted text to o1.txt with a newline
    with open(os.path.join(desktop_path, "o1.txt"), "a") as output_file:
        output_file.write(extracted_text + "\n")
    
    # Delete the screenshot file after processing
    os.remove(file_path)

initial_files = set(os.listdir(desktop_path))

while True:
    # Get the current list of files
    current_files = set(os.listdir(desktop_path))
    
    # Find new files
    new_files = current_files - initial_files
    
    for file_name in new_files:
        if file_name.startswith("Screenshot") and file_name.endswith(".png"):
            file_path = os.path.join(desktop_path, file_name)
            run_tesseract(file_path)
    
    # Update the initial list of files
    initial_files = current_files
    
    # Wait for a while before checking again
    time.sleep(10)