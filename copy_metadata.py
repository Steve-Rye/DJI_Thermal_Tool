import os
import argparse
import tempfile
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Union
from tqdm import tqdm

"""
DJI Image Metadata Copy Tool

Description:
---------
Reads all metadata from metadata file (metadata.txt) and copies it to corresponding TIFF files.
Ensures all geotags and camera information are correctly copied.
"""

class MetadataCopier:
    """Metadata copier"""
    def __init__(self):
        """Initialize copier"""
        self.exiftool_path = self._find_exiftool()

        try:
            subprocess.run(
                [self.exiftool_path, "-ver"],
                capture_output=True,
                check=True
            )
            self.exiftool_available = True
            print(f"ExifTool successfully detected: {self.exiftool_path}")
        except (subprocess.SubprocessError, FileNotFoundError):
            print("Warning: ExifTool not found. Will use limited metadata copying method.")
            self.exiftool_available = False
    def _find_exiftool(self) -> str:
        """
        Locate ExifTool executable path

        Returns:
            str: Path to ExifTool executable
        """
        root_dir = Path(__file__).resolve().parent

        exiftool_dir = root_dir / "exiftool-13.29_64"
        exiftool_windows = exiftool_dir / "exiftool.exe"
        exiftool_unix = exiftool_dir / "exiftool"
        exiftool_asset = (
            root_dir / "Thermal-Tools-main" / "assets" /
            "linux" / "exiftool" / "exiftool"
        )
        exiftool_packages = sorted(
            exiftool_dir.glob("Image-ExifTool-*/exiftool"),
            reverse=True
        )

        if sys.platform.startswith("win"):
            if exiftool_windows.exists():
                return str(exiftool_windows)
        else:
            if exiftool_unix.exists():
                exiftool_unix.chmod(0o755)
                return str(exiftool_unix)
            for pkg_exe in exiftool_packages:
                pkg_exe.chmod(0o755)
                return str(pkg_exe)
            if exiftool_asset.exists():
                exiftool_asset.chmod(0o755)
                return str(exiftool_asset)
            if exiftool_windows.exists():
                exiftool_windows.chmod(0o755)
                return str(exiftool_windows)

        return "exiftool.exe" if sys.platform.startswith("win") else "exiftool"
    def _load_metadata(self, metadata_file: Path) -> Dict[str, Dict[str, str]]:
        """
        Load metadata from metadata.txt

        Args:
            metadata_file: Path to metadata file

        Returns:
            Dict[str, Dict[str, str]]: Metadata dictionary with image names as keys
        """
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

        metadata_dict = {}
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            header = f.readline().strip().split(',')
            if not header or header[0] != 'ImageName':
                raise ValueError(f"Invalid metadata file format: {metadata_file}")

            for line in f:
                values = line.strip().split(',')
                if len(values) >= len(header):
                    image_name = values[0]
                    metadata = {header[i]: values[i] for i in range(1, len(header))}
                    metadata_dict[image_name] = metadata

        return metadata_dict

    def _find_matching_pairs(self, folder_path: Path) -> List[Tuple[Path, Path]]:
        """
        Find matching JPG and TIFF image pairs in directory

        Args:
            folder_path: Folder path

        Returns:
            List[Tuple[Path, Path]]: List of JPG and TIFF file path pairs
        """
        input_dir = folder_path / "input_dir"
        if not input_dir.exists() or not input_dir.is_dir():
            print(f"Warning: Input directory not found {input_dir}")
            return []

        output_dir = folder_path / "out_dir"
        if not output_dir.exists() or not output_dir.is_dir():
            print(f"Warning: Output directory not found {output_dir}")
            return []

        jpg_files = {f.stem: f for f in input_dir.glob('*.jpg')}
        jpg_files.update({f.stem: f for f in input_dir.glob('*.JPG')})
        
        tiff_files = {f.stem: f for f in output_dir.glob('*.tiff')}
        tiff_files.update({f.stem: f for f in output_dir.glob('*.TIFF')})

        matches = []
        for stem, jpg_path in jpg_files.items():
            if stem in tiff_files:
                matches.append((jpg_path, tiff_files[stem]))

        return matches

    def _copy_metadata_to_tiff(
        self, jpg_path: Path, tiff_path: Path, metadata: Dict[str, str]
    ) -> bool:
        """
        Copy metadata to TIFF file

        Args:
            jpg_path: JPG file path
            tiff_path: TIFF file path
            metadata: Metadata dictionary

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not tiff_path.exists():
                print(f"Error: TIFF file not found: {tiff_path.absolute()}")
                return False

            if self.exiftool_available:
                cmd = [
                    self.exiftool_path,
                    "-overwrite_original",
                    "-TagsFromFile", str(jpg_path),
                    "-all:all",
                    "-unsafe",
                    str(tiff_path)
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    print(f"Warning: exiftool failed to copy metadata: {result.stderr}")
                    return False

                xmp_tags = {}
                for tag, value in metadata.items():
                    if tag.startswith('Xmp.'):
                        xmp_tags[tag] = value
                
                if xmp_tags:
                    with tempfile.NamedTemporaryFile(
                        mode='w', suffix='.txt', delete=False
                    ) as temp_file:
                        temp_path = temp_file.name
                        for tag, value in xmp_tags.items():
                            clean_tag = tag.replace('Xmp.', '')
                            temp_file.write(f"-XMP:{clean_tag}={value}\n")

                    xmp_cmd = [
                        self.exiftool_path,
                        "-overwrite_original",
                        "-@ " + temp_path,
                        str(tiff_path)
                    ]

                    xmp_result = subprocess.run(xmp_cmd, capture_output=True, text=True)

                    os.remove(temp_path)

                    if xmp_result.returncode != 0:
                        print(f"Warning: exiftool failed to add XMP tags: {xmp_result.stderr}")

                return True
            else:
                print(f"Using fallback method to copy metadata to: {tiff_path.name}")
                return False

        except Exception as e:
            print(f"Error: Unable to copy metadata to {tiff_path.name}: {str(e)}")
            return False

    def process_folder(self, folder_path: Union[str, Path]) -> Tuple[int, int]:
        """
        Process images in a single folder

        Args:
            folder_path: Folder path

        Returns:
            Tuple[int, int]: (success_count, total_count)
        """
        folder_path = Path(folder_path)
        
        metadata_file = folder_path / "metadata.txt"
        try:
            metadata_dict = self._load_metadata(metadata_file)
        except Exception as e:
            print(f"Error: Failed to load metadata - {str(e)}")
            return (0, 0)

        matches = self._find_matching_pairs(folder_path)
        if not matches:
            print(f"Warning: No matching images found - {folder_path.name}")
            return (0, 0)

        print(f"Found {len(matches)} pairs of matching images")
        
        success_count = 0
        pbar_desc = f"Copying metadata - {folder_path.name}"
        with tqdm(matches, desc=pbar_desc, mininterval=1.0) as pbar:
            for jpg_path, tiff_path in pbar:
                jpg_name = jpg_path.name
                
                if jpg_name in metadata_dict:
                    if self._copy_metadata_to_tiff(
                        jpg_path, tiff_path, metadata_dict[jpg_name]
                    ):
                        success_count += 1

        return (success_count, len(matches))

    def process_all(self, root_dir: str = "main") -> None:
        """
        Process all subfolders under root directory

        Args:
            root_dir: Root directory path, default is 'main'
        """
        root_path = Path(root_dir)
        if not root_path.exists():
            print(f"Error: Root directory not found - {root_dir}")
            return

        subfolders = [f for f in root_path.iterdir() if f.is_dir()]

        if not subfolders:
            print("No subfolders found, processing current directory")
            success, total = self.process_folder(root_path)
            if total > 0:
                print(f"Completed {root_path.name}: success {success}/{total}")
            return

        print(f"Found {len(subfolders)} subfolders")

        for folder in subfolders:
            success, total = self.process_folder(folder)
            if total > 0:
                print(f"Completed {folder.name}: success {success}/{total}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="DJI Image Metadata Copy Tool")
    parser.add_argument("-d", "--directory",
                      default="main",
                      help="Specify root directory path to process (default is 'main')")
    
    args = parser.parse_args()
    
    copier = MetadataCopier()
    try:
        print(f"\nProcessing directory: {args.directory}")
        copier.process_all(args.directory)
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    main()