import os
import sys
import subprocess

def create_directory_structure():
    print("Creating directory structure...")
    
    directories = [
        "knowledge_graph",
        "poison_generator",
        "poison_enhancer",
        "poison_merger",
        "output",
        "logs"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        init_file = os.path.join(directory, "__init__.py")
        if not os.path.exists(init_file) and directory not in ["output", "logs"]:
            with open(init_file, "w", encoding="utf-8") as f:
                f.write(f'"""\n{directory.replace("_", " ").title()} Module\n"""\n')
    
    print("Directory structure created!")

def install_requirements():
    print("Installing dependencies...")
    
    requirements = [
        "networkx",
        "requests",
    ]
    
    with open("requirements.txt", "w", encoding="utf-8") as f:
        for req in requirements:
            f.write(f"{req}\n")
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Dependencies installed!")
    except subprocess.CalledProcessError:
        print("Warning: Error installing dependencies, please run manually: pip install -r requirements.txt")

def main():
    print("Starting setup for poisoned knowledge graph generation project...")
    
    create_directory_structure()
    
    install_requirements()
    
    print("\nProject setup complete!")
    print("You can run the project with the following commands:")
    print("- Run the entire process: python main.py")
    print("- Run only knowledge graph construction: python main.py --run-graph")
    print("- Run only poisoned text generation: python main.py --run-generator")
    print("- Run only poisoned text enhancement: python main.py --run-enhancer")
    print("- Run only poisoned text merging: python main.py --run-merger")

if __name__ == "__main__":
    main()