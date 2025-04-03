import subprocess
import os

def save_libraries(file_name="requirements.txt"):
    """
    Saves all installed libraries in the current environment to a requirements file.
    """
    try:
        print(f"Saving libraries to {file_name}...")
        result = subprocess.run(["pip", "freeze"], capture_output=True, text=True, check=True)
        with open(file_name, "w") as file:
            file.write(result.stdout)
        print(f"Libraries saved to {file_name}.")
    except Exception as e:
        print(f"Failed to save libraries: {e}")

def install_libraries(file_name="requirements.txt"):
    """
    Installs libraries from the specified requirements file.
    """
    if not os.path.exists(file_name):
        print(f"Requirements file '{file_name}' not found.")
        return
    try:
        print(f"Installing libraries from {file_name}...")
        subprocess.run(["pip", "install", "-r", file_name], check=True)
        print("Libraries installed successfully.")
    except Exception as e:
        print(f"Failed to install libraries: {e}")

if __name__ == "__main__":
    print("1: Save libraries\n2: Install libraries\n3: Exit")
    choice = input("Choose an option: ")

    if choice == "1":
        save_libraries()
    elif choice == "2":
        install_libraries()
    elif choice == "3":
        print("Exiting...")
    else:
        print("Invalid choice.")
