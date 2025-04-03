import os
import magic  # For detecting file types
import difflib  # For similarity comparison
from pathlib import Path

# Function to search for files by keywords
def search_by_keywords(base_directory, keywords, filetype=None):
    """
    Search for files in a directory by keywords in filename or metadata.
    Optionally filter by filetype.
    """
    matching_files = []
    keywords = [kw.lower() for kw in keywords]  # Normalize keywords for comparison
    
    for root, dirs, files in os.walk(base_directory):
        for file in files:
            # Check if the filename matches keywords
            file_lower = file.lower()
            if any(kw in file_lower for kw in keywords):
                # Optionally check for filetype
                if filetype and not file.lower().endswith(filetype.lower()):
                    continue
                matching_files.append(os.path.join(root, file))
    
    return matching_files

def extract_shorthand_directory(keywords):
    common_dirs = {
        "downloads": os.path.expanduser("~/Downloads"),
        "desktop": os.path.expanduser("~/Desktop"),
        "documents": os.path.expanduser("~/Documents"),
    }
    for word in keywords:
        if word.lower() in common_dirs:
            return common_dirs[word.lower()]
    return os.getcwd()  # Default to current directory



# Function to search for files similar to a base file
def search_by_similarity(base_file, directory, threshold=0.5):
    """
    Find files similar to a base file based on content similarity.
    Only compares files of the same type.
    """
    if not os.path.exists(base_file):
        raise FileNotFoundError(f"Base file not found: {base_file}")
    
    # Detect file type of the base file
    file_type = magic.Magic(mime=True).from_file(base_file)
    base_content = read_file_content(base_file)
    
    similar_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            
            # Ensure the file is of the same type
            if magic.Magic(mime=True).from_file(file_path) != file_type:
                continue
            
            # Compare content similarity
            file_content = read_file_content(file_path)
            similarity = compare_content_similarity(base_content, file_content)
            
            if similarity >= threshold:
                similar_files.append((file_path, similarity))
    
    # Sort by similarity score (highest first)
    similar_files.sort(key=lambda x: x[1], reverse=True)
    return similar_files


# Helper function to read file content
def read_file_content(file_path):
    """
    Read the content of a file. Handles text and binary files.
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        with open(file_path, 'rb') as f:
            return f.read()


# Helper function to compare content similarity
def compare_content_similarity(content1, content2):
    """
    Compare the similarity of two pieces of content using difflib.
    """
    if isinstance(content1, bytes):
        content1 = content1.decode('utf-8', errors='ignore')
    if isinstance(content2, bytes):
        content2 = content2.decode('utf-8', errors='ignore')
    
    return difflib.SequenceMatcher(None, content1, content2).ratio()


def resolve_directory(name):
    """
    Resolves directory shorthand to its full path. Tries common directories,
    relative paths, and home directory expansions.
    """
    known_dirs = {
        "desktop": os.path.expanduser("~/Desktop"),
        "downloads": os.path.expanduser("~/Downloads"),
        "documents": os.path.expanduser("~/Documents"),
        "pictures": os.path.expanduser("~/Pictures"),
        "music": os.path.expanduser("~/Music"),
        "videos": os.path.expanduser("~/Videos"),
    }

    # Try resolving known common directories
    if name.lower() in known_dirs:
        return known_dirs[name.lower()]

    # Try resolving relative to the current working directory
    relative_path = os.path.join(os.getcwd(), name)
    if os.path.isdir(relative_path):
        return os.path.abspath(relative_path)

    # Try resolving relative to the user's home directory
    home_path = os.path.expanduser(f"~/{name}")
    if os.path.isdir(home_path):
        return os.path.abspath(home_path)

    # If not found, return the name as-is (may be invalid)
    return name
