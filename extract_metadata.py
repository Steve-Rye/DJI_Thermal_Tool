import os
import subprocess
import shutil
import tempfile
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from tqdm import tqdm

"""
DJI Image Metadata Extraction Tool

Description:
---------
Extract metadata from DJI camera JPG images, including:
- All XMP and EXIF tags containing 'dji', 'GPS', 'image', 'rtk' or 'thermal' keywords (case insensitive)
- Export all matching tags and their values to txt file with filename as first column

Supported Devices:
- Zenmuse H20T
- Zenmuse H20N
- Zenmuse H30T
- Zenmuse XT S
- M2EA (Mavic 2 Enterprise Advanced)
- M30T
- M3T
- M3TD (newly added)
- M4T (newly added)
"""

class MetadataProcessor:
    """Image metadata processor"""

    def __init__(self):
        """Initialize processor"""
        self.temp_dir = self._create_temp_dir()
        self.all_tags = set(['ImageName'])

        self.exiftool_path = self._find_exiftool()

        self._check_exiftool()

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

    def _check_exiftool(self) -> None:
        """Check if ExifTool is available"""
        try:
            subprocess.run(
                [self.exiftool_path, "-ver"],
                capture_output=True,
                check=True
            )
            print(f"ExifTool successfully detected: {self.exiftool_path}")
        except (subprocess.SubprocessError, FileNotFoundError):
            error_msg = (
                "Error: ExifTool not found or cannot run."
                "Please ensure ExifTool is properly installed and added to system path."
            )
            raise RuntimeError(error_msg)

    def _create_temp_dir(self) -> Path:
        """
        Create temporary working directory

        Returns:
            Path: Temporary directory path
        """
        try:
            temp_base = Path(tempfile.gettempdir())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_dir = temp_base / f'metadata_process_{timestamp}'
            temp_dir.mkdir(parents=True, exist_ok=True)
            return temp_dir
        except Exception as e:
            print(f"Warning: Cannot use system temporary directory ({str(e)})")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            fallback_dir = Path.cwd() / f'temp_metadata_{timestamp}'
            fallback_dir.mkdir(parents=True, exist_ok=True)
            return fallback_dir

    def extract_metadata(self, jpg_path: Union[str, Path]) -> Optional[Dict[str, str]]:
        """
        Extract metadata from a single JPG file
        
        Args:
            jpg_path: JPG file path
            
        Returns:
            Optional[Dict[str, str]]: Extracted metadata dictionary, returns None if extraction fails
        """
        temp_jpg = None
        try:
            jpg_path = Path(jpg_path)
            temp_jpg = self.temp_dir / f"temp_{jpg_path.name}"
            
            shutil.copy2(str(jpg_path), str(temp_jpg))
            
            cmd = [self.exiftool_path, "-j", "-G", "-a", str(temp_jpg)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            import json
            data = json.loads(result.stdout)
            if not data or len(data) == 0:
                print(f"Warning: No metadata found in {jpg_path.name}")
                return None
            
            metadata = {'ImageName': jpg_path.name}
            
            keywords = ['dji', 'gps', 'image', 'rtk', 'thermal']
            
            for tag_full_name, value in data[0].items():
                if ":" in tag_full_name:
                    group, tag = tag_full_name.split(":", 1)
                    tag_lower = tag.lower()

                    skip_tags = [
                        'SourceFile', 'Directory', 'FileSize',
                        'FileModifyDate', 'FileAccessDate',
                        'FileInodeChangeDate'
                    ]
                    if tag_full_name in skip_tags:
                        continue
                    
                    if any(keyword in tag_lower for keyword in keywords):
                        full_tag = f"{group}.{tag}"
                        
                        str_value = str(value).lstrip('+')
                        metadata[full_tag] = str_value
                        self.all_tags.add(full_tag)
            
            if len(metadata) <= 1:
                print(f"Warning: No matching metadata found in {jpg_path.name}")
                return None
                
            return metadata
                
        except Exception as e:
            print(f"Error: Error occurred while processing {jpg_path.name} ({str(e)})")
            return None
        finally:
            if temp_jpg and temp_jpg.exists():
                try:
                    temp_jpg.unlink()
                except Exception:
                    pass

    def save_to_txt(
        self, data: List[Dict[str, str]], folder_path: Union[str, Path]
    ) -> None:
        """
        Save metadata to metadata.txt file

        Args:
            data: Metadata list
            folder_path: Output folder path
        """
        if not data:
            return

        output_path = Path(folder_path) / "metadata.txt"

        other_tags = sorted(list(self.all_tags - {'ImageName'}))
        fieldnames = ['ImageName'] + other_tags

        print(f"\nNumber of tags found: {len(fieldnames)}")
        
        with output_path.open('w', encoding='utf-8') as txtfile:
            txtfile.write(','.join(fieldnames) + '\n')
            
            for row in data:
                values = []
                for field in fieldnames:
                    values.append(str(row.get(field, '')))
                txtfile.write(','.join(values) + '\n')
        
        print(f"Generated: {output_path}")

    @staticmethod
    def find_subfolders(base_dir: Union[str, Path]) -> List[Path]:
        """
        Find all subfolders
        
        Args:
            base_dir: Base directory path
            
        Returns:
            List[Path]: List of found subfolder paths
        """
        subfolders = []
        base_dir = Path(base_dir)
        
        if not base_dir.is_dir():
            return subfolders
        
        try:
            for item in base_dir.iterdir():
                if item.is_dir():
                    subfolders.append(item)
        except Exception as e:
            print(f"Warning: Error occurred while searching folders ({str(e)})")
        
        return subfolders

    def process_folder(self, folder_path: Union[str, Path]) -> None:
        """
        Process all JPG files in a single folder
        
        Args:
            folder_path: Folder path to process
        """
        folder_path = Path(folder_path)
        
        if not folder_path.is_dir():
            print(f"Error: {folder_path} is not a valid directory")
            return
        
        other_dir = folder_path / "other"
        if not other_dir.exists():
            other_dir.mkdir(parents=True, exist_ok=True)
            
        input_dir = folder_path / "input_dir"
        if not input_dir.exists():
            input_dir.mkdir(parents=True, exist_ok=True)
            
        jpg_files_lower = list(input_dir.glob('*.jpg'))
        jpg_files_upper = list(input_dir.glob('*.JPG'))
        existing_input_files = jpg_files_lower + jpg_files_upper
        if existing_input_files:
            msg = (
                f"Detected {len(existing_input_files)} JPG files already existing in input directory {input_dir}, "
                f"continuing to process these files"
            )
            print(msg)
            jpg_files = existing_input_files
            total_imgs = len(jpg_files)
            print(f"Processing {total_imgs} thermal photos in {folder_path.name}")
            
            all_metadata = []
            
            with tqdm(jpg_files, desc="Extracting metadata", mininterval=1.0) as pbar:
                for jpg_file in pbar:
                    metadata = self.extract_metadata(jpg_file)
                    if metadata:
                        all_metadata.append(metadata)
            
            if all_metadata:
                print(f"\nExtracted metadata from {len(all_metadata)}/{total_imgs} files")
                self.save_to_txt(all_metadata, folder_path)
            else:
                print(f"Warning: Unable to extract metadata from any image in {folder_path.name}.")
            return
        
        jpg_files = []
        for item in folder_path.iterdir():
            if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg']:
                jpg_files.append(item)
        
        if not jpg_files:
            print(f"Warning: No JPG files found in {folder_path}")
            return
            
        thermal_files = []
        non_thermal_files = []
        
        for jpg_file in jpg_files:
            if jpg_file.exists():
                filename = jpg_file.name
                upper_name = filename.upper()
                is_thermal = (
                    upper_name.endswith('T.JPG') or
                    upper_name.endswith('INFRA.JPG')
                )
                if is_thermal:
                    thermal_files.append(jpg_file)
                else:
                    non_thermal_files.append(jpg_file)
                
        if non_thermal_files:
            print(f"Found {len(non_thermal_files)} non-thermal photos, moving to {other_dir.name} folder")
            moved_count = 0
            for file in non_thermal_files:
                if file.exists():
                    try:
                        target_path = other_dir / file.name
                        if not target_path.exists():
                            shutil.move(str(file), str(target_path))
                            moved_count += 1
                        else:
                            print(f"Skipping existing file: {file.name}")
                    except Exception as e:
                        print(f"Warning: Failed to move file {file.name}: {str(e)})")
            print(f"Successfully moved {moved_count} non-thermal photos")
            print(f"All non-thermal photos moved to {other_dir}, no metadata extraction")
        
        if not thermal_files:
            print(f"Warning: No thermal photos found in {folder_path} (files ending with 'T.JPG' or 'INFRA.JPG')")
            return
            
        print(f"Found {len(thermal_files)} thermal photos, moving to {input_dir.name} folder")
        moved_count = 0
        for file in thermal_files:
            if file.exists():
                try:
                    target_path = input_dir / file.name
                    if not target_path.exists():
                        shutil.move(str(file), str(target_path))
                        moved_count += 1
                    else:
                        print(f"Skipping existing file: {file.name}")
                except Exception as e:
                    print(f"Warning: Failed to move file {file.name}: {str(e)}")
        print(f"Successfully moved {moved_count} thermal photos")
                
        jpg_files = list(input_dir.glob('*.jpg')) + list(input_dir.glob('*.JPG'))
            
        total_imgs = len(jpg_files)
        if total_imgs == 0:
            print(f"Warning: No JPG files found in {input_dir}, cannot continue processing")
            return
            
        print(f"Processing {total_imgs} thermal photos in {folder_path.name}")
        
        all_metadata = []
        
        with tqdm(jpg_files, desc="Extracting metadata", mininterval=1.0) as pbar:
            for jpg_file in pbar:
                metadata = self.extract_metadata(jpg_file)
                if metadata:
                    all_metadata.append(metadata)
        
        if all_metadata:
            print(f"\nExtracted metadata from {len(all_metadata)}/{total_imgs} files")
            self.save_to_txt(all_metadata, folder_path)
        else:
            print(f"Warning: Unable to extract metadata from any image in {folder_path.name}.")

    def process_all(self, root_dir: str = "main") -> None:
        """
        Process all subfolders in specified directory
        
        Args:
            root_dir: Root directory path, default is 'main'
        """
        try:
            root_path = Path(root_dir)
            if not root_path.exists():
                print(f"Error: Directory not found - {root_dir}")
                return
                
            subfolders = self.find_subfolders(root_path)
            
            if not subfolders:
                print("No subfolders found, processing current directory")
                self.process_folder(root_path)
                return
                
            print(f"Found {len(subfolders)} subfolders")
            
            for folder in subfolders:
                self.process_folder(folder)
            
        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            try:
                if self.temp_dir.exists():
                    shutil.rmtree(self.temp_dir)
            except Exception as e:
                print(f"Warning: Failed to clean up temporary files ({str(e)})")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="DJI Image Metadata Extraction Tool")
    parser.add_argument("-d", "--directory",
                      default="main",
                      help="Specify the root directory path to process (default: 'main')")
    
    args = parser.parse_args()
    
    processor = MetadataProcessor()
    processor.process_all(args.directory)

if __name__ == "__main__":
    main()