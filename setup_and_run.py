import subprocess
import os
import sys

def run_command(cmd, description):
    print(f"\n{'='*60}")
    print(f"📦 {description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0

def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         OMNIRoute-DM - Complete Setup                    ║
    ║                                                          ║
    ║  This script will:                                       ║
    ║  1. Generate synthetic delivery data                     ║
    ║  2. Train Machine Learning models                        ║
    ║  3. Start the web dashboard                              ║
    ║                                                          ║
    ║  Make sure MySQL is running before continuing!           ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    input("Press Enter to start...")
    
    # Step 1: Generate data
    if not run_command("python data/generate_delivery_data.py", "Step 1: Generating Data"):
        print("\n❌ Data generation failed!")
        sys.exit(1)
    
    # Step 2: Train models
    if not run_command("python backend/models/train_model.py", "Step 2: Training Models"):
        print("\n❌ Model training failed!")
        sys.exit(1)
    
    # Step 3: Start backend
    print("\n" + "="*60)
    print("🚀 Step 3: Starting Flask Backend")
    print("="*60)
    print("\nThe dashboard will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop the server\n")
    
    # Open browser
    import webbrowser
    webbrowser.open("http://localhost:5000")
    
    # Start Flask
    subprocess.run("python backend/app.py", shell=True)

if __name__ == "__main__":
    main()