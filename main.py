import os
import argparse
from extract_metadata import MetadataProcessor
from jpg2tiff import ImageProcessor
from copy_metadata import MetadataCopier

"""
DJI Thermal Image Processing Tool

Description:
---------
Execute the following processing in order:
1. Extract image metadata (extract_metadata.py)
   - Identify thermal photos with filename suffix "T.JPG" or "INFRA.JPG"
   - Move other photos to other folder (no processing on these photos)
   - Move thermal photos to input_dir folder and extract metadata
2. Convert JPG to TIFF (jpg2tiff.py)
   - Convert thermal photos in input_dir to TIFF format
   - Save converted TIFF files to out_dir folder
3. Copy metadata to TIFF (copy_metadata.py)
   - Copy metadata from original JPG to converted TIFF files
"""

class ProcessManager:
    """Process manager"""
    
    def __init__(self, directory: str):
        """
        Initialize process manager
        
        Args:
            directory: Directory path to process
        """
        self.directory = directory

    def run_all(self) -> None:
        """
        Execute all processing steps in order
        """
        try:
            print("\n===== Step 1: Extract Metadata =====")
            metadata_processor = MetadataProcessor()
            metadata_processor.process_all(self.directory)

            print("\n===== Step 2: Convert Image Format =====")
            image_processor = ImageProcessor()
            image_processor.process_subfolders(self.directory)

            print("\n===== Step 3: Copy Metadata =====")
            metadata_copier = MetadataCopier()
            metadata_copier.process_all(self.directory)

            print("\n===== All Processing Complete! =====")

        except Exception as e:
            print(f"\nError: Exception occurred during processing: {str(e)}")
            raise

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="DJI Thermal Image Processing Tool")
    parser.add_argument("-d", "--directory",
                       default="main",
                       help="Specify root directory path to process (default is 'main')")
    parser.add_argument("-q", "--quiet", 
                      action="store_true",
                      help="Quiet mode, reduce output information")

    args = parser.parse_args()

    if not args.quiet:
        print("DJI Thermal Image Processing Tool")
        print("====================")
        print(f"Processing directory: {args.directory}\n")

    if not os.path.exists(args.directory):
        print(f"Error: Directory does not exist - {args.directory}")
        return

    try:
        manager = ProcessManager(args.directory)
        manager.run_all()
    except Exception as e:
        print(f"\nProcessing failed: {str(e)}")
        return

if __name__ == "__main__":
    main()