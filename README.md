# Image → Harmonized Palette

A web application that extracts harmonized color palettes from images using perceptually uniform color spaces.

## Features

- Upload any image to extract its color palette
- Select specific regions of an image to extract palettes from
- Automatic determination of color harmony schemes (analogous, complementary, etc.)
- Visual palette display with color roles (primary, secondary, tertiary, support)
- Export palettes as text files

## How It Works

This application uses weighted K-means clustering in the OKLab color space to extract color palettes from images. OKLab is a perceptually uniform color space that better represents how humans perceive color differences.

The algorithm:
1. Converts images to OKLab color space
2. Applies weighted K-means clustering (weighting by perceived luminance)
3. Merges similar colors
4. Selects primary, secondary, and tertiary colors
5. Determines the best color harmony scheme
6. Identifies supporting colors

## Requirements

- Python 3.8+
- FastAPI
- Uvicorn
- Pillow
- NumPy
- Scikit-learn

## Running the Project

### 1. Clone the Repository

```bash
git clone <repository-url>
cd image-palette
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
uvicorn app:app --reload
```

The application will be available at `http://localhost:8000`

### 5. Access the Application

Open your web browser and navigate to `http://localhost:8000`

## Project Structure

```
image-palette/
├── app.py                 # Main FastAPI application
├── requirements.txt       # Dependencies
├── palette/               # Core palette extraction logic
│   ├── color.py           # Color space conversions (OKLab, RGB)
│   ├── extract.py         # Palette extraction algorithm
│   └── region.py          # Image cropping functionality
├── static/                # Frontend assets
│   ├── index.html         # Main HTML page
│   ├── style.css          # CSS styling
│   └── app.js             # JavaScript frontend logic
└── *.jpg                  # Sample images
```

## API Endpoints

- `GET /` - Serve the main web page
- `POST /api/palette` - Extract palette from uploaded image
- `POST /api/palette/region` - Extract palette from a specific region of the image

## Usage

1. Click "Upload image" to select an image file
2. The application will automatically extract and display the palette
3. Drag on the image to select a region and extract a palette from that area
4. Click on color swatches in the top right to copy their hex codes
5. Click "Export palette" to download the palette as a text file

## License

MIT