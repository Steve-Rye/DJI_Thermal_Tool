# AI Agent Guidelines for DJI Thermal Tool Project

## Project Overview

**Project Type:** Image Processing Tool - Thermal Imaging Data Conversion  
**Purpose:** Convert DJI thermal camera JPG images to TIFF format with temperature data for use in Pix4Dmapper  
**Language:** Python 3.9+  
**Package Manager:** uv (with pyproject.toml)

**Key Technologies:**
- **Core Libraries:** Pillow, NumPy, piexif, tqdm
- **External Dependencies:** 
  - ExifTool (metadata extraction/copying)
  - DJI Thermal SDK v1.7 (thermal data extraction)

**Supported Devices:**
- DJI Zenmuse: H20T, H20N, H30T, XT S
- DJI Mavic: M2EA, M30T, M3T, M3TD, M4T

## Coding Standards

### Python Style Guide

1. **Follow PEP 8** for code formatting
2. **Type Hints:** Use type annotations for function parameters and return values
   ```python
   def process_folder(self, folder_path: Union[str, Path]) -> None:
   ```

3. **Imports Organization:**
   - Standard library imports first
   - Third-party imports second
   - Local imports last
   - Group related imports together

4. **Docstrings:** Use triple-quoted strings for all classes and functions
   - Include parameter descriptions
   - Include return value descriptions

5. **Error Handling:**
   - Use try-except blocks for file operations
   - Always clean up resources (temp files, directories) in finally blocks
   - Never silently ignore errors - at minimum, log warnings

### Code Consistency

1. **Match Existing Patterns:**
   - Review similar functions before implementing new features
   - Use the same error message format: `"Error: ..."` or `"Warning: ..."`
   - Follow existing naming conventions (snake_case for functions/variables)

2. **Class Structure:**
   - Use classes for processors/managers (MetadataProcessor, ImageProcessor)
   - Initialize external tool paths in `__init__`
   - Separate public methods from private methods (use `_` prefix for private)

3. **Progress Reporting:**
   - Use `tqdm` for long-running operations
   - Set `mininterval=1.0` to avoid excessive updates
   - Provide clear descriptions: `desc="Extracting metadata"`

## Project Structure

### Directory Layout

```
DJI_Thermal_Tool/
├── main.py                           # Unified entry point
├── extract_metadata.py                # Step 1: Extract and organize images
├── jpg2tiff.py                        # Step 2: Convert JPG to TIFF
├── copy_metadata.py                   # Step 3: Copy metadata to TIFF
├── pyproject.toml                     # Package configuration
├── uv.lock                            # Dependency lock file
├── README.md                          # User documentation
├── AGENTS.md                          # This file
├── dji_thermal_sdk_v1.7_20241205/     # DJI Thermal SDK
└── exiftool-13.29_64/                 # ExifTool binary

Working Directory Structure (created during processing):
main/
└── mission_01/                        # User-created mission folder
    ├── input_dir/                     # Thermal JPG images (moved here)
    ├── out_dir/                       # Converted TIFF files (output)
    ├── other/                         # Non-thermal images (moved here)
    ├── metadata.txt                   # Extracted metadata (CSV format)
    └── temp_dir/                      # Temporary files (auto-deleted)
```

### Processing Pipeline

The tool follows a strict 3-step pipeline:

1. **extract_metadata.py** - Organize and extract metadata
   - Identify thermal images (`*_T.JPG`, `*_INFRA.JPG`)
   - Move thermal images to `input_dir/`
   - Move non-thermal images to `other/`
   - Extract GPS, camera, and thermal metadata to `metadata.txt`

2. **jpg2tiff.py** - Convert image format
   - Process images from `input_dir/`
   - Use DJI Thermal SDK to extract temperature data
   - Convert to TIFF format (temperature in 0.1°C units)
   - Save to `out_dir/`

3. **copy_metadata.py** - Preserve metadata
   - Copy all EXIF/XMP tags from JPG to TIFF using ExifTool
   - Preserve GPS coordinates, camera parameters, gimbal orientation

## Development Guidelines

### Working with External Tools

1. **ExifTool Path Resolution:**
   - Check multiple possible locations (see `_find_exiftool()` in extract_metadata.py)
   - Handle both Windows (.exe) and Linux (Unix binary) versions
   - Set executable permissions on Linux: `chmod 0o755`
   - Always verify tool availability with version check

2. **DJI Thermal SDK Usage:**
   - SDK path determined by platform (Windows/Linux)
   - Set `LD_LIBRARY_PATH` (Linux) or `PATH` (Windows) for shared libraries
   - Suppress SDK output: `stdout=devnull, stderr=devnull`
   - Handle SDK errors gracefully

3. **Platform-Specific Code:**
   - Use `platform.system()` to detect OS
   - Use `Path` objects for cross-platform file paths
   - Test on both Windows and Linux when making changes

### File Operations

1. **Always use Path objects** from pathlib for file paths
2. **Check existence** before operations: `if path.exists():`
3. **Create directories safely:** `path.mkdir(parents=True, exist_ok=True)`
4. **Clean up temp files** in finally blocks
5. **Preserve original files** - only move/copy, never delete originals

### Testing Approach

Since this tool processes real thermal images:

1. **Prepare test data:**
   - Use small sample of actual DJI thermal images
   - Include both `*_T.JPG` and `*_INFRA.JPG` formats
   - Test with different camera models if possible

2. **Validation steps:**
   - Verify all input files are processed
   - Check output TIFF files contain temperature data
   - Confirm metadata is preserved (use ExifTool to inspect)
   - Test in Pix4Dmapper if available

3. **Error scenarios to test:**
   - Missing ExifTool or SDK
   - Corrupted input images
   - Insufficient disk space
   - Permission errors

## Git Workflow

### Commit Message Style

Follow the existing pattern (check `git log`):
- Use descriptive, imperative mood messages
- Examples: "Fix image path reference", "Add support for M4T camera"

### Before Committing

1. **Review changes:** `git diff` and `git status`
2. **Check for sensitive data:** No API keys, credentials, or personal data
3. **Test the changes:** Run through the full processing pipeline
4. **Update documentation:** If adding features or changing behavior

## Dependencies Management

### Adding New Dependencies

Use `uv add` to add dependencies (automatically updates `pyproject.toml` and `uv.lock`):

```bash
# Add a new package
uv add <package-name>

# Add with version constraint
uv add "numpy>=1.22.0"

# Add as development dependency
uv add --dev pytest
```

**Verify compatibility:**
- Check Python version requirements (>=3.9, <3.13)
- Test on both Windows and Linux if possible

### Removing Dependencies

```bash
uv remove <package-name>
```

### Syncing Dependencies

After cloning or when `pyproject.toml` is modified externally:

```bash
uv sync
```

### Updating Dependencies

```bash
# Update all dependencies to latest compatible versions
uv lock --upgrade

# Update specific package
uv lock --upgrade-package <package-name>
```

### Checking Installed Packages

```bash
# List all installed packages
uv pip list

# Show dependency tree
uv tree

# Check lock file
cat uv.lock
```


**Last Updated:** 2025-10-25  
**Project Version:** 1.7.0
**Maintainer:** Steve-Rye