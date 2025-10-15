import os
import shutil
import platform
import subprocess
import argparse
import stat
from typing import Any
from PIL import Image
import piexif
from tqdm import tqdm
import numpy as np
from pathlib import Path

"""
DJI Image Batch Processing Tool - Simplified Version
Automatically process DJI camera image data:
1. JPG to TIFF format conversion
2. File classification and organization

Supported Devices:
- Zenmuse H20T
- Zenmuse H20N
- Zenmuse H30T
- Zenmuse XT S
- M2EA (Mavic 2 Enterprise Advanced)
- M30T
- M3T
- M3TD
- M4T
"""

class ImageProcessor:
    """Image processor"""

    INPUT_DIR_NAME = "input_dir"
    OUTPUT_DIR_NAME = "out_dir"
    TEMP_DIR_NAME = "temp_dir"

    SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")

    def __init__(self):
        """Initialize processor and determine running platform"""
        self.platform = platform.system()

        self.sdk_path = self._get_sdk_path()
        self._ensure_sdk_executable()
        print(f"DJI Thermal SDK path: {self.sdk_path}")
    def _get_sdk_path(self) -> str:
        """
        Get DJI SDK executable path

        Returns:
            str: Path to SDK executable
        """
        script_dir = Path(__file__).resolve().parent

        if self.platform == "Windows":
            sdk_exe = "dji_irp.exe"
            sdk_rel_path = (
                Path("dji_thermal_sdk_v1.7_20241205") / "utility" /
                "bin" / "windows" / "release_x64" / sdk_exe
            )
        elif self.platform == "Linux":
            sdk_exe = "dji_irp"
            sdk_rel_path = (
                Path("dji_thermal_sdk_v1.7_20241205") / "utility" /
                "bin" / "linux" / "release_x64" / sdk_exe
            )
        else:
            sdk_exe = "dji_irp"
            sdk_rel_path = (
                Path("dji_thermal_sdk_v1.7_20241205") / "utility" /
                "bin" / "linux" / "release_x64" / sdk_exe
            )

        full_path = script_dir / sdk_rel_path

        if not full_path.exists():
            sdk_rel_path = sdk_rel_path.as_posix().replace("v1.7_20241205", "v1.5_20240507")
            full_path = script_dir / sdk_rel_path
            if not full_path.exists():
                print(f"Warning: DJI SDK not found: {full_path}")

        return str(full_path)

    def _ensure_sdk_executable(self) -> None:
        """Ensure SDK executable has execution permissions on Unix-like systems"""
        if self.platform not in {"Linux", "Darwin"}:
            return

        sdk_file = Path(self.sdk_path)
        if not sdk_file.exists():
            return

        if os.access(sdk_file, os.X_OK):
            return

        try:
            current_mode = sdk_file.stat().st_mode
            sdk_file.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except PermissionError as exc:
            raise RuntimeError(
                f"SDK executable lacks execution permissions and cannot be automatically fixed: {sdk_file}"
            ) from exc

    def process_subfolders(self, parent_dir: str = "main") -> None:
        """Process all subfolders under specified parent directory"""
        if not os.path.exists(parent_dir):
            raise FileNotFoundError(f"Parent directory not found: {parent_dir}")

        subfolders = [f for f in os.listdir(parent_dir)
                     if os.path.isdir(os.path.join(parent_dir, f))]
        
        if not subfolders:
            print(f"No subfolders found in {parent_dir}")
            return
            
        for subfolder in subfolders:
            subfolder_path = os.path.join(parent_dir, subfolder)
            print(f"\nProcessing: {subfolder}")
            self._process_single_folder(subfolder_path)

    def _process_single_folder(self, folder_path: str) -> None:
        """Process a single thermal folder"""
        input_dir = os.path.join(folder_path, self.INPUT_DIR_NAME)
        if not os.path.exists(input_dir):
            print(f"Warning: Input directory not found {input_dir}, creating empty directory")
            os.makedirs(input_dir)
            
        output_dir = self._create_directory(folder_path, self.OUTPUT_DIR_NAME)
        temp_dir = self._create_directory(folder_path, self.TEMP_DIR_NAME)

        try:
            image_files = [f for f in os.listdir(input_dir) 
                          if f.lower().endswith(self.SUPPORTED_IMAGE_EXTENSIONS)]
                          
            if not image_files:
                print(f"Warning: No image files found in {input_dir}")
                return
                
            first_file = image_files[0]
            first_input_path = os.path.join(input_dir, first_file)
            first_file_stem = os.path.splitext(first_file)[0]
            first_raw_path = os.path.join(temp_dir, f"{first_file_stem}.raw")

            devnull = subprocess.DEVNULL

            self._convert_with_dji_sdk(first_input_path, first_raw_path, devnull)

            with Image.open(first_input_path) as img:
                width, height = img.size

            img_data = np.fromfile(first_raw_path, dtype='int16')
            actual_pixels = img_data.size

            if actual_pixels != width * height:
                ratio = width / height
                new_height = int(np.sqrt(actual_pixels / ratio))
                new_width = int(actual_pixels / new_height)

                while new_width * new_height != actual_pixels:
                    new_height -= 1
                    new_width = int(actual_pixels / new_height)

                msg = (
                    f"Note: Thermal data size({new_width}x{new_height})"
                    f"differs from RGB image size({width}x{height})"
                )
                print(msg)
                thermal_width, thermal_height = new_width, new_height
                ImageProcessor._last_thermal_size = (
                    thermal_width, thermal_height
                )

            first_output = os.path.join(
                output_dir, f"{os.path.splitext(first_file)[0]}.tiff"
            )
            self._process_raw_image(first_raw_path, first_output, first_input_path)
            
            remaining_files = image_files[1:]
            total_count = len(image_files)
            processed_count = 1
            
            with tqdm(total=total_count, initial=processed_count, desc="Conversion progress", mininterval=1.0) as pbar:
                for filename in remaining_files:
                    input_path = os.path.join(input_dir, filename)
                    raw_path = os.path.join(temp_dir, f"{os.path.splitext(filename)[0]}.raw")
                    output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.tiff")
                    
                    self._convert_with_dji_sdk(input_path, raw_path, devnull)
                    self._process_raw_image(raw_path, output_path, input_path)
                    pbar.update(1)
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def _create_directory(self, parent_path: str, dir_name: str) -> str:
        """Create directory, delete if already exists"""
        dir_path = os.path.join(parent_path, dir_name)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
        os.makedirs(dir_path)
        return dir_path

    def _convert_with_dji_sdk(
        self, input_path: str, raw_path: str, devnull: Any
    ) -> None:
        """Use DJI Thermal SDK to convert image"""
        input_path_abs = str(Path(input_path).absolute())
        raw_path_abs = str(Path(raw_path).absolute())

        sdk_cmd = (
            f'"{self.sdk_path}" -s "{input_path_abs}" '
            f'-a measure -o "{raw_path_abs}"'
        )

        sdk_dir = Path(self.sdk_path).resolve().parent
        extra_lib_dir = (
            Path(__file__).resolve().parent /
            "tsdk-core" / "lib" / "linux" / "release_x64"
        )

        env = os.environ.copy()
        lib_paths = [str(sdk_dir)]
        if extra_lib_dir.exists():
            lib_paths.append(str(extra_lib_dir))
        existing = env.get("LD_LIBRARY_PATH")
        if existing:
            lib_paths.append(existing)
        env["LD_LIBRARY_PATH"] = ":".join(lib_paths)

        if self.platform == "Windows":
            win_paths = [str(sdk_dir)]
            existing_path = env.get("PATH")
            if existing_path:
                win_paths.append(existing_path)
            env["PATH"] = ";".join(win_paths)
        
        if self.platform == "Windows":
            try:
                subprocess.run(
                    sdk_cmd,
                    shell=True,
                    stdout=devnull,
                    stderr=devnull,
                    check=True,
                    env=env
                )
            except subprocess.CalledProcessError as e:
                print(f"Warning: SDK call failed: {e}")
        else:
            subprocess.run(
                sdk_cmd,
                shell=True,
                stdout=devnull,
                stderr=devnull,
                check=True,
                env=env
            )

    def _process_raw_image(self, raw_path: str, output_path: str, original_image_path: str) -> None:
        """Process RAW format temperature data and save as TIFF"""
        with Image.open(original_image_path) as img:
            width, height = img.size
        
        img_data = np.fromfile(raw_path, dtype='int16')
        
        expected_pixels = width * height
        actual_pixels = img_data.size
        
        if not hasattr(ImageProcessor, '_last_thermal_size'):
            ImageProcessor._last_thermal_size = None
        
        if actual_pixels != expected_pixels:
            ratio = width / height
            new_height = int(np.sqrt(actual_pixels / ratio))
            new_width = int(actual_pixels / new_height)
            
            while new_width * new_height != actual_pixels:
                new_height -= 1
                new_width = int(actual_pixels / new_height)
            
            width, height = new_width, new_height

        img_data = img_data.reshape(height, width) / 10

        exif_dict = piexif.load(original_image_path)
        new_exif = {
            '0th': {},
            'Exif': {},
            'GPS': exif_dict['GPS'],
            'Interop': {},
            '1st': {},
            'thumbnail': exif_dict['thumbnail']
        }
        exif_bytes = piexif.dump(new_exif)
        
        Image.fromarray(img_data).save(output_path, exif=exif_bytes)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DJI Image Batch Processing Tool - Simplified Version")
    parser.add_argument("-d", "--directory",
                      default="main",
                      help="Specify root directory path to process (default is 'main')")
    
    args = parser.parse_args()
    
    processor = ImageProcessor()
    try:
        print(f"\nProcessing directory: {args.directory}")
        processor.process_subfolders(args.directory)
    except Exception as e:
        print(f"\nError: {str(e)}")