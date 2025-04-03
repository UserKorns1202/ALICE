import os
import shutil
import difflib
from pathlib import Path
from collections import defaultdict
from mimetypes import guess_type


# Function to get the file type (based on extension or mime type)
def get_file_type(file_path):
    # Using mimetypes to determine the file type
    mime_type, _ = guess_type(file_path)
    if mime_type:
        return mime_type.split('/')[0]  # Return 'image', 'text', 'audio', etc.
    else:
        return 'unknown'


# Function to calculate similarity between files based on their names
def calculate_similarity(file_name, reference_name):
    # Calculate similarity between the file name and a reference name
    return difflib.SequenceMatcher(None, file_name.lower(), reference_name.lower()).ratio()


# Function to sort files by similarity to a reference file name
def sort_by_similarity(directory, reference_name):
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    sorted_files = defaultdict(list)
    
    for file in files:
        similarity = calculate_similarity(file, reference_name)
        sorted_files[round(similarity, 2)].append(file)  # Group files by similarity score
    
    # Sort similarity groups by similarity
    return sorted(sorted_files.items(), reverse=True)


# Function to sort files by type
def sort_by_file_type(directory):
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    sorted_files = defaultdict(list)
    
    for file in files:
        file_type = get_file_type(os.path.join(directory, file))
        sorted_files[file_type].append(file)
    
    # Sort file groups by file type
    return sorted(sorted_files.items(), key=lambda x: x[0])


# Function to create new folders and move the files
def organize_files(directory, sorted_files):
    for folder_name, files in sorted_files:
        # Create a new folder for this group if it doesn't exist
        folder_path = os.path.join(directory, folder_name)
        Path(folder_path).mkdir(parents=True, exist_ok=True)
        
        for file in files:
            # Move the file to the new folder
            file_path = os.path.join(directory, file)
            new_file_path = os.path.join(folder_path, file)
            shutil.move(file_path, new_file_path)
            print(f"Moved {file} to {folder_name}")


# Main function to execute sorting and organizing files
def sort_directory(directory, criteria="type", reference_name=None):
    if not os.path.isdir(directory):
        print(f"The provided path {directory} is not a valid directory.")
        return
    
    if criteria == "similarity" and reference_name:
        sorted_files = sort_by_similarity(directory, reference_name)
    elif criteria == "type":
        sorted_files = sort_by_file_type(directory)
    else:
        print("Invalid criteria. Use 'type' or 'similarity'.")
        return
    
    organize_files(directory, sorted_files)
    print("Sorting complete.")


# Example usage:
# sort_directory('/path/to/directory', criteria='similarity', reference_name='example_file_name')
# or
# sort_directory('/path/to/directory', criteria='type')
